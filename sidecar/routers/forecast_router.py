from fastapi import APIRouter
from typing import Optional
from db.manager import db_manager
from agents.forecast_agent import forecast_agent
from models.api_models import ForecastResponse

router = APIRouter(prefix="/forecast", tags=["Demand Forecast"])

@router.get("/", response_model=ForecastResponse)
async def get_forecast(fiscal_year: str, asset_group: Optional[str] = None):
    """
    Computes the annual supply demand for a given Fiscal Year (AGT-03).
    Formula: Demand = ((Total Capacity + 10% Top-up) × Service Frequency per Year) × Asset Quantity × 1.20 Buffer
    """
    conn = db_manager.connect()
    
    # In a real scenario, we would query 'components' or 'fluid_types' tables.
    # For this phase, we aggregate assets to get counts and apply the formula to 'Engine Oil' as an example.
    
    query = "SELECT COUNT(*) FROM assets"
    params = []
    if asset_group:
        query += " WHERE asset_group = ?"
        params.append(asset_group)
    
    asset_count = conn.execute(query, params).fetchone()[0]
    
    if asset_count == 0:
        return {"fiscal_year": fiscal_year, "items": []}

    # Example: Engine Oil Forecast
    # Capacity = 20L, Frequency = 2 per year
    demand = forecast_agent.calculate_fluid_demand(20, 2, asset_count)
    
    return {
        "fiscal_year": fiscal_year,
        "items": [
            {
                "category": "Fluid",
                "description": "Engine Oil (SAE 15W-40)",
                "quantity": demand["quantity"],
                "unit": "Liters",
                "formula_breakdown": demand["formula_breakdown"]
            }
        ]
    }
