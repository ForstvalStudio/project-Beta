import logging
import uuid
from datetime import datetime, date
from typing import Dict, Any, Optional
from db.manager import db_manager

logger = logging.getLogger("sidecar.lifecycle")


class AssetLifecycleManager:
    """
    Manages higher-level business logic for asset lifecycles.
    Uses ACTUAL live DB column names: overhaul_id (TEXT PK), type (not overhaul_type).
    """

    @staticmethod
    def calculate_vintage(commission_date_str: str) -> float:
        """Vintage = (Today - Commission Date) in decimal years. Rule L08."""
        try:
            comm_dt = datetime.strptime(commission_date_str[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return 0.0
        delta = (date.today() - comm_dt).days
        return round(delta / 365.25, 2)

    def get_overhaul_params(self, asset_group: str) -> Dict[str, Any]:
        """
        Determine overhaul trigger parameters based on asset_group.
        New equipment types from 164_f.xlsx: Gen set, JCB, Dozer, SSL
        
        Returns: {"years": int|None, "kms": int|None, "hrs": int|None}
        """
        if not asset_group:
            return {"years": 15, "kms": None, "hrs": None}
        
        group_upper = asset_group.upper()
        
        # MTL (Mine Truck Large) - 30 years
        if "MTL" in group_upper:
            return {"years": 30, "kms": None, "hrs": None}
        
        # ALS - 9 years or 100,000 kms
        if "ALS" in group_upper:
            return {"years": 9, "kms": 100000, "hrs": None}
        
        # MG, Gypsy - 9 years
        if "MG" in group_upper or "GYPSY" in group_upper:
            return {"years": 9, "kms": None, "hrs": None}
        
        # Gen set, JCB, Dozer, SSL - HRS only, 8 years (use BOH column if present)
        if any(x in group_upper for x in ["GEN", "JCB", "DOZER", "SSL"]):
            return {"years": 8, "kms": None, "hrs": None}
        
        # MSS, TATRA, CT, PM - 12 years or 60,000 kms
        if any(x in group_upper for x in ["MSS", "TATRA", "CT", "PM"]):
            return {"years": 12, "kms": 60000, "hrs": None}
        
        # BMP, AERV - 15 years
        if "BMP" in group_upper or "AERV" in group_upper:
            return {"years": 15, "kms": None, "hrs": None}
        
        # Default - 15 years
        return {"years": 15, "kms": None, "hrs": None}

    def schedule_initial_overhaul(
        self, 
        ba_number: str, 
        commission_date_str: str,
        asset_group: str = ""
    ):
        """
        OH-I scheduled based on equipment type rules. LOGIC.md §3.1.
        
        Equipment-specific triggers:
        - MTL: 30 years
        - ALS: 9 years or 100,000 kms
        - MG/Gypsy: 9 years
        - Gen set/JCB/Dozer/SSL: 8 years (HRS-only)
        - MSS/TATRA/CT/PM: 12 years or 60,000 kms
        - BMP/AERV: 15 years
        - Default: 15 years
        """
        try:
            comm_dt = datetime.strptime(commission_date_str[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            logger.error(f"Invalid commission_date for {ba_number}: {commission_date_str!r}")
            return

        params = self.get_overhaul_params(asset_group)
        years = params.get("years", 15)
        
        oh1_date = comm_dt.replace(year=comm_dt.year + years)
        overhaul_id = f"OHL-{ba_number}-OH1"

        conn = db_manager.connect()
        try:
            # Check if already exists (idempotent)
            existing = conn.execute(
                "SELECT overhaul_id FROM overhauls WHERE overhaul_id = ?", (overhaul_id,)
            ).fetchone()
            if existing:
                logger.info(f"OH-I already scheduled for {ba_number} — skipping")
                return

            # Store trigger criteria in status field for reference
            trigger_info = f"{years}Y"
            if params.get("kms"):
                trigger_info += f"/{params['kms']//1000}K"
            
            conn.execute("""
                INSERT INTO overhauls (overhaul_id, ba_number, type, overhaul_type, scheduled_date, status)
                VALUES (?, ?, 'OH-I', 'OH-I', ?, ?)
            """, (overhaul_id, ba_number, oh1_date.strftime("%Y-%m-%d"), trigger_info))
            conn.commit()
            logger.info(f"Scheduled OH-I for {ba_number} ({asset_group}) on {oh1_date} " +
                       f"trigger={trigger_info} (id={overhaul_id})")
        except Exception as e:
            logger.error(f"Failed to schedule OH-I for {ba_number}: {e}")

    def schedule_next_overhaul(self, ba_number: str, previous_type: str, completion_date_str: str):
        """
        OH-II = 10 years after OH-I. Discard = 10 years after OH-II. LOGIC.md §3.2/3.3.
        """
        try:
            comp_dt = datetime.strptime(completion_date_str[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            logger.error(f"Invalid completion_date for {ba_number}: {completion_date_str!r}")
            return

        next_map = {"OH-I": ("OH-II", "OHL-{ba}-OH2"), "OH-II": ("DISCARD", "OHL-{ba}-DSC")}
        if previous_type not in next_map:
            logger.warning(f"No next lifecycle step for {previous_type}")
            return

        next_type, id_template = next_map[previous_type]
        overhaul_id = id_template.replace("{ba}", ba_number)
        next_date = comp_dt.replace(year=comp_dt.year + 10)

        conn = db_manager.connect()
        try:
            conn.execute("""
                INSERT INTO overhauls (overhaul_id, ba_number, type, overhaul_type, scheduled_date, status)
                VALUES (?, ?, ?, ?, ?, 'Scheduled')
            """, (overhaul_id, ba_number, next_type, next_type, next_date.strftime("%Y-%m-%d")))
            conn.commit()
            logger.info(f"Scheduled {next_type} for {ba_number} on {next_date}")
        except Exception as e:
            logger.error(f"Failed to schedule {next_type} for {ba_number}: {e}")

    def trigger_monthly_rollover(self):
        """
        Monthly usage rollover. LOGIC.md §1.5:
        previous_month_kms = current_month_kms, current_month_kms = 0
        """
        logger.info("Executing monthly usage rollover...")
        conn = db_manager.connect()
        try:
            conn.execute("""
                UPDATE assets
                SET previous_month_kms = current_month_kms,
                    current_month_kms = 0,
                    updated_at = CURRENT_TIMESTAMP
            """)
            conn.execute("""
                INSERT INTO agent_audit_log (agent_id, action, action_type, status)
                VALUES ('SYS', 'Monthly Usage Rollover', 'rollover', 'success')
            """)
            conn.commit()
            logger.info("Monthly rollover complete")
        except Exception as e:
            logger.error(f"Monthly rollover failed: {e}")
            raise


lifecycle_manager = AssetLifecycleManager()
