from fastapi import APIRouter, Depends, HTTPException
from typing import List
from datetime import datetime
from db.manager import db_manager
from logic.auth import get_current_user, check_admin
from logic.lifecycle import lifecycle_manager
from models.api_models import AssetCreate, AssetResponse

router = APIRouter(prefix="/assets", tags=["Assets"])

@router.post("/", response_model=AssetResponse)
async def create_asset(asset_in: AssetCreate, user: dict = Depends(check_admin)):
    """
    Creates a new asset and automatically schedules OH-I.
    Admin only.
    """
    conn = db_manager.connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO assets (ba_number, serial_number, asset_group, asset_type, commission_date, total_kms, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (asset_in.ba_number, asset_in.serial_number, asset_in.asset_group, asset_in.asset_type, 
                 asset_in.commission_date, asset_in.total_kms, asset_in.status)
            )
        
        # Rule L04: Schedule OH-I automatically
        lifecycle_manager.schedule_initial_overhaul(asset_in.ba_number, asset_in.commission_date)
        
        # Calculate vintage for response
        vintage = lifecycle_manager.calculate_vintage(asset_in.commission_date)
        
        return {
            **asset_in.dict(),
            "current_month_kms": 0.0,
            "previous_month_kms": 0.0,
            "created_at": datetime.utcnow(),
            "vintage": vintage
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[AssetResponse])
async def list_assets(user: dict = Depends(get_current_user)):
    """
    Lists all assets.
    Accessible to all logged-in users.
    """
    conn = db_manager.connect()
    rows = conn.execute("SELECT * FROM assets").fetchall()
    
    # Map rows to response models including vintage calculation
    assets = []
    for r in rows:
        vintage = lifecycle_manager.calculate_vintage(r[4]) # index 4 is commission_date
        assets.append({
            "ba_number": r[0], "serial_number": r[1], "asset_group": r[2], "asset_type": r[3],
            "commission_date": r[4], "total_kms": r[5], "current_month_kms": r[6],
            "previous_month_kms": r[7], "status": r[8], "created_at": r[9],
            "vintage": vintage
        })
    return assets
