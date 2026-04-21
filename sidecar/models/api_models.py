from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime

# --- Auth Models ---

class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    role: str

class UserBase(BaseModel):
    username: str
    full_name: Optional[str] = None
    role: str = "USER"

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# --- Asset Models ---

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
    current_month_kms: float
    previous_month_kms: float
    created_at: datetime
    vintage: float # Computed field

# --- Maintenance Models ---

class TaskBase(BaseModel):
    id: str
    ba_number: str
    task_description: str
    due_date: str
    status: str = "Scheduled"

class TaskCompleteRequest(BaseModel):
    completion_date: str
    meterage_at_completion: float

class TaskResponse(TaskBase):
    scheduled_date: Optional[str] = None
    completion_date: Optional[str] = None
    status_colour: str # Computed

# --- Forecast Models ---

class ForecastItem(BaseModel):
    category: str
    description: str
    quantity: float
    unit: str
    formula_breakdown: Dict[str, float]

class ForecastResponse(BaseModel):
    fiscal_year: str
    items: List[ForecastItem]
