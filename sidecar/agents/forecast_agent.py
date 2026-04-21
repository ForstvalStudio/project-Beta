import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("sidecar.agents.forecast_agent")

class ForecastAgent:
    """
    AGT-03 — ForecastAgent
    Identity: Deterministic calculation agent.
    Role: Computes annual supply demand for a given Fiscal Year.
    """

    # MANDATORY safety multiplier — hardcoded
    SAFETY_BUFFER = 1.20

    def calculate_fluid_demand(self, 
                               total_capacity: float, 
                               service_frequency: float, 
                               asset_count: int) -> Dict[str, Any]:
        """
        Calculates demand for a single fluid category.
        
        Formula:
        Demand = ((Total Capacity + 10% Top-up) × Service Frequency) × Asset Quantity × 1.20 Buffer
        """
        top_up_factor = 1.10  # 10% top-up
        
        base_demand = (total_capacity * top_up_factor) * service_frequency
        total_demand = base_demand * asset_count * self.SAFETY_BUFFER
        
        result = {
            "quantity": round(total_demand, 2),
            "formula_breakdown": {
                "capacity": total_capacity,
                "top_up": round(total_capacity * 0.10, 2),
                "frequency": service_frequency,
                "asset_count": asset_count,
                "buffer": self.SAFETY_BUFFER,
                "total": round(total_demand, 2)
            }
        }
        
        return result

# Global instance
forecast_agent = ForecastAgent()
