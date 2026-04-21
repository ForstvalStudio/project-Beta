from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from agents.forecast_agent import forecast_agent
from models.api_models import ForecastResponse

router = APIRouter(prefix="/forecast", tags=["Demand Forecast"])


@router.get("/", response_model=ForecastResponse)
async def get_forecast(
    fiscal_year: str = Query(..., description="Fiscal year format: YYYY-YY e.g. 2024-25"),
    asset_group: Optional[str] = Query(None, description="Filter by asset group")
):
    """
    AGT-03 — Computes annual supply demand for a given Fiscal Year.
    Formula: (Capacity + 10% Top-up) x Frequency x Asset Count x 1.20 Buffer
    Buffer 1.20 is hardcoded per GR-B01.
    """
    try:
        result = forecast_agent.compute(fiscal_year, asset_group)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
