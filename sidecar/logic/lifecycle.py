import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from db.manager import db_manager

logger = logging.getLogger("sidecar.lifecycle")

class AssetLifecycleManager:
    """
    Manages higher-level business logic for asset lifecycles:
    - Monthly usage rollovers
    - Overhaul auto-scheduling
    - Vintage calculations
    """

    @staticmethod
    def calculate_vintage(commission_date: str) -> float:
        """
        Computes the vintage (age) in decimal years.
        Rule L08: Vintage = (Current Date - Commission Date) in years.
        """
        try:
            comm_dt = datetime.strptime(commission_date, "%Y-%m-%d").date()
        except ValueError:
            comm_dt = datetime.fromisoformat(commission_date.replace("Z", "+00:00")).date()
            
        today = datetime.now().date()
        delta_days = (today - comm_dt).days
        vintage = delta_days / 365.25
        return round(vintage, 2)

    def trigger_monthly_rollover(self):
        """
        Executes the monthly usage rollover.
        Rule L07: 
        1. previous_month_kms = current_month_kms
        2. current_month_kms = 0
        """
        logger.info("Executing monthly usage rollover...")
        conn = db_manager.connect()
        try:
            with conn:
                # Update all assets in a single atomic transaction
                conn.execute("""
                    UPDATE assets 
                    SET previous_month_kms = current_month_kms,
                        current_month_kms = 0
                """)
                # Log audit record
                conn.execute("""
                    INSERT INTO agent_audit_log (agent_id, action, status)
                    VALUES ('SYS', 'Monthly Usage Rollover', 'SUCCESS')
                """)
            logger.info("Monthly rollover complete")
        except Exception as e:
            logger.error(f"Monthly rollover failed: {e}")
            raise

    def schedule_initial_overhaul(self, ba_number: str, commission_date: str):
        """
        Schedules the OH-I overhaul (15 years after commission).
        Rule L04: OH-I occurs at 15 years of age.
        """
        try:
            comm_dt = datetime.strptime(commission_date, "%Y-%m-%d").date()
        except ValueError:
            comm_dt = datetime.fromisoformat(commission_date.replace("Z", "+00:00")).date()

        oh1_date = comm_dt.replace(year=comm_dt.year + 15)
        
        conn = db_manager.connect()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO overhauls (ba_number, overhaul_type, scheduled_date, status)
                    VALUES (?, 'OH-I', ?, 'Scheduled')
                """, (ba_number, oh1_date.strftime("%Y-%m-%d")))
            logger.info(f"Scheduled OH-I for {ba_number} on {oh1_date}")
        except Exception as e:
            logger.error(f"Failed to schedule OH-I for {ba_number}: {e}")
            raise

    def schedule_next_overhaul(self, ba_number: str, previous_type: str, completion_date: str):
        """
        Schedules the next step in the overhaul lifecycle.
        Rule L05: OH-II occurs 10 years after OH-I completion.
        Rule L06: Discard occurs 10 years after OH-II completion.
        """
        try:
            comp_dt = datetime.strptime(completion_date, "%Y-%m-%d").date()
        except ValueError:
            comp_dt = datetime.fromisoformat(completion_date.replace("Z", "+00:00")).date()

        next_type = None
        if previous_type == "OH-I":
            next_type = "OH-II"
            interval = 10
        elif previous_type == "OH-II":
            next_type = "DISCARD"
            interval = 10
        
        if not next_type:
            logger.warning(f"No next lifecycle step for overhaul type: {previous_type}")
            return

        next_date = comp_dt.replace(year=comp_dt.year + interval)
        
        conn = db_manager.connect()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO overhauls (ba_number, overhaul_type, scheduled_date, status)
                    VALUES (?, ?, ?, 'Scheduled')
                """, (ba_number, next_type, next_date.strftime("%Y-%m-%d")))
            logger.info(f"Scheduled {next_type} for {ba_number} on {next_date}")
        except Exception as e:
            logger.error(f"Failed to schedule {next_type} for {ba_number}: {e}")
            raise

# Global instance
lifecycle_manager = AssetLifecycleManager()
