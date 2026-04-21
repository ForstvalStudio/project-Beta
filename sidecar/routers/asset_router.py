from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime
from db.manager import db_manager
from logic.lifecycle import lifecycle_manager
from models.api_models import AssetCreate, AssetResponse

router = APIRouter(prefix="/assets", tags=["Assets"])


def _row_to_asset(r) -> dict:
    """
    Maps a sqlite3.Row to the AssetResponse dict using named column access.
    Handles both the original column names (name, date_of_commission, kms)
    and the schema.sql canonical names (ba_number, commission_date, total_kms)
    since the live DB has both due to the self-healing sync adding columns.
    """
    d = dict(r)

    # ba_number: canonical column, may fall back to legacy 'name'
    ba_number = d.get("ba_number") or d.get("name") or ""

    # commission_date: canonical, fallback to legacy 'date_of_commission'
    commission_date = (
        d.get("commission_date") or d.get("date_of_commission")
        or datetime.utcnow().strftime("%Y-%m-%d")
    )

    # total_kms: canonical, fallback to legacy 'kms' or 'total_meterage'
    total_kms = float(
        d.get("total_kms")
        or d.get("kms")
        or d.get("total_meterage")
        or 0.0
    )

    vintage = lifecycle_manager.calculate_vintage(commission_date)

    return {
        "ba_number":           ba_number,
        "serial_number":       d.get("serial_number") or "",
        "asset_group":         d.get("asset_group") or "",
        "asset_type":          d.get("asset_type") or "",
        "commission_date":     commission_date,
        "total_kms":           total_kms,
        "current_month_kms":   float(d.get("current_month_kms") or 0.0),
        "previous_month_kms":  float(d.get("previous_month_kms") or 0.0),
        "status":              d.get("status") or "Active",
        "created_at":          d.get("created_at") or datetime.utcnow().isoformat(),
        "vintage":             vintage,
    }


@router.post("/", response_model=AssetResponse)
async def create_asset(asset_in: AssetCreate):
    """Creates a new asset and automatically schedules OH-I."""
    conn = db_manager.connect()
    try:
        conn.execute("""
            INSERT INTO assets (
                ba_number, serial_number, asset_group, asset_type,
                commission_date, total_kms, current_month_kms, previous_month_kms, status
            ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?)
        """, (
            asset_in.ba_number, asset_in.serial_number, asset_in.asset_group,
            asset_in.asset_type, asset_in.commission_date,
            asset_in.total_kms, asset_in.status,
        ))
        conn.commit()

        # Rule L04: Schedule OH-I automatically
        lifecycle_manager.schedule_initial_overhaul(asset_in.ba_number, asset_in.commission_date)

        vintage = lifecycle_manager.calculate_vintage(asset_in.commission_date)
        return {
            **asset_in.model_dump(),
            "current_month_kms": 0.0,
            "previous_month_kms": 0.0,
            "created_at": datetime.utcnow(),
            "vintage": vintage,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[AssetResponse])
async def list_assets(search: Optional[str] = Query(None, description="Filter by BA number, group, or type")):
    """Lists all assets from SQLite. Supports optional search filter."""
    conn = db_manager.connect()

    if search:
        pattern = f"%{search}%"
        rows = conn.execute("""
            SELECT * FROM assets
            WHERE ba_number LIKE ? OR asset_group LIKE ? OR asset_type LIKE ? OR serial_number LIKE ?
            ORDER BY created_at DESC
        """, (pattern, pattern, pattern, pattern)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM assets ORDER BY created_at DESC").fetchall()

    return [_row_to_asset(r) for r in rows]


@router.get("/{ba_number}", response_model=AssetResponse)
async def get_asset(ba_number: str):
    """Returns full detail for a single asset by BA number."""
    conn = db_manager.connect()
    row = conn.execute(
        "SELECT * FROM assets WHERE ba_number = ?", (ba_number,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Asset '{ba_number}' not found")
    return _row_to_asset(row)
