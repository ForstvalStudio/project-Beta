from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ── Asset Models ──────────────────────────────────────────────────────────────

class AssetBase(BaseModel):
    ba_number: str
    serial_number: Optional[str] = None
    asset_group: Optional[str] = None
    asset_type: Optional[str] = None
    commission_date: str
    total_kms: float = 0.0
    status: str = "Active"


class AssetCreate(AssetBase):
    pass


class AssetResponse(AssetBase):
    current_month_kms: float = 0.0
    previous_month_kms: float = 0.0
    created_at: Any  # str or datetime
    vintage: float   # computed

    class Config:
        from_attributes = True


# ── Maintenance Task Models ───────────────────────────────────────────────────

class TaskBase(BaseModel):
    id: str
    ba_number: str
    task_description: str
    due_date: str
    status: str = "Scheduled"


class TaskCompleteRequest(BaseModel):
    completion_date: str
    meterage_at_completion: float = 0.0


class TaskResponse(TaskBase):
    scheduled_date: Optional[str] = None
    completion_date: Optional[str] = None
    status_colour: str = "#009900"


# ── Forecast Models ───────────────────────────────────────────────────────────

class ForecastItem(BaseModel):
    category: str
    description: str
    quantity: float
    unit: str
    formula_breakdown: Dict[str, Any]


class ForecastResponse(BaseModel):
    fiscal_year: str
    items: List[ForecastItem]
    asset_count: int = 0
