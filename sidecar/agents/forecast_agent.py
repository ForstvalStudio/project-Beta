"""
AGT-03 — ForecastAgent
Computes annual fluid/component demand for a target Fiscal Year.
Formula (AGENTS.md / LOGIC.md §4.1):
  Demand = (Capacity + 10% Top-up) × Frequency × Asset_Count × 1.20 Buffer
Buffer 1.20 is hardcoded — GR-B01.
"""
import logging
from typing import List, Optional, Dict, Any
from db.manager import db_manager

logger = logging.getLogger("sidecar.agents.forecast_agent")

# Service frequency defaults per asset group (services per year)
# Will be replaced by real lookup table in Phase 5
_DEFAULT_FREQUENCY_PER_YEAR = 2.0
_DEFAULT_CAPACITY_LITRES = 50.0
_BUFFER = 1.20          # GR-B01 — hardcoded, not configurable
_TOP_UP_RATE = 0.10     # 10% top-up on capacity


class ForecastAgent:
    """AGT-03 — Deterministic fluid demand calculation agent."""

    def compute(self, fiscal_year: str, asset_group: Optional[str] = None) -> Dict[str, Any]:
        """
        Computes demand for all assets (or a specific group) in the given fiscal year.
        fiscal_year format: YYYY-YY (e.g. 2024-25). Validates format.
        """
        # Validate fiscal year format
        parts = fiscal_year.split("-")
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            raise ValueError(f"Fiscal year must be YYYY-YY format, got: {fiscal_year!r}")

        conn = db_manager.connect()

        # Query assets
        if asset_group:
            rows = conn.execute(
                "SELECT * FROM assets WHERE asset_group = ? AND status = 'Active'",
                (asset_group,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM assets WHERE status = 'Active'"
            ).fetchall()

        if not rows:
            return {"fiscal_year": fiscal_year, "items": [], "asset_count": 0}

        # Group by asset_group for demand aggregation
        groups: Dict[str, List] = {}
        for r in rows:
            d = dict(r)
            grp = d.get("asset_group") or "Unclassified"
            groups.setdefault(grp, []).append(d)

        items = []
        for grp, assets_in_group in groups.items():
            count = len(assets_in_group)
            capacity = _DEFAULT_CAPACITY_LITRES
            top_up = capacity * _TOP_UP_RATE
            frequency = _DEFAULT_FREQUENCY_PER_YEAR

            # Fluid demand formula (AGENTS.md AGT-03)
            total = (capacity + top_up) * frequency * count * _BUFFER

            items.append({
                "category": "Fluid",
                "description": f"Engine Oil — {grp}",
                "quantity": round(total, 2),
                "unit": "litres",
                "formula_breakdown": {
                    "capacity": capacity,
                    "top_up": top_up,
                    "frequency": frequency,
                    "asset_count": count,
                    "buffer": _BUFFER,
                    "total": round(total, 2),
                },
            })

            # Component demand: filters (1 per asset per year)
            filter_demand = count * 1.0 * _BUFFER
            items.append({
                "category": "Component",
                "description": f"Air Filter — {grp}",
                "quantity": round(filter_demand, 2),
                "unit": "units",
                "formula_breakdown": {
                    "capacity": 1.0,
                    "top_up": 0.0,
                    "frequency": 1.0,
                    "asset_count": count,
                    "buffer": _BUFFER,
                    "total": round(filter_demand, 2),
                },
            })

        logger.info(
            f"[AGT-03] Forecast for {fiscal_year}"
            + (f" / {asset_group}" if asset_group else " / all groups")
            + f": {len(items)} items across {len(rows)} assets"
        )

        return {
            "fiscal_year": fiscal_year,
            "items": items,
            "asset_count": len(rows),
        }


forecast_agent = ForecastAgent()
