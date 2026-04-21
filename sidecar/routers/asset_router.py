from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime
from db.manager import db_manager
from logic.lifecycle import lifecycle_manager
from models.api_models import AssetCreate, AssetResponse

router = APIRouter(prefix="/assets", tags=["Assets"])


def _row_to_asset(r) -> dict:
    """
    Maps a sqlite3.Row to AssetResponse using named column access.
    Canonical names: ba_number, name, date_of_commission, kms.
    commission_date and total_kms are alias columns — read both.
    """
    d = dict(r)

    # Commission date: prefer canonical date_of_commission, fallback to commission_date
    commission_date = (
        d.get("date_of_commission")
        or d.get("commission_date")
        or datetime.utcnow().strftime("%Y-%m-%d")
    )

    # KMs: prefer kms (original), fallback to total_kms
    kms = float(d.get("kms") or d.get("total_kms") or 0.0)

    return {
        "ba_number":           d.get("ba_number") or "",
        "serial_number":       d.get("serial_number") or "",
        "asset_group":         d.get("asset_group") or "",
        "asset_type":          d.get("asset_type") or "",
        "commission_date":     commission_date,
        "total_kms":           kms,
        "current_month_kms":   float(d.get("current_month_kms") or 0.0),
        "previous_month_kms":  float(d.get("previous_month_kms") or 0.0),
        "status":              d.get("status") or "Active",
        "created_at":          d.get("created_at") or datetime.utcnow().isoformat(),
        "vintage":             lifecycle_manager.calculate_vintage(commission_date),
    }


@router.get("/", response_model=List[AssetResponse])
async def list_assets(
    search: Optional[str] = Query(None, description="Filter by BA, group, type, or serial")
):
    """Lists all assets from SQLite. Optional search filter."""
    conn = db_manager.connect()
    if search:
        p = f"%{search}%"
        rows = conn.execute("""
            SELECT * FROM assets
            WHERE ba_number LIKE ? OR asset_group LIKE ? OR asset_type LIKE ? OR serial_number LIKE ? OR name LIKE ?
            ORDER BY created_at DESC
        """, (p, p, p, p, p)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM assets ORDER BY created_at DESC").fetchall()

    return [_row_to_asset(r) for r in rows]


@router.get("/{ba_number}", response_model=AssetResponse)
async def get_asset(ba_number: str):
    """Returns full detail for a single asset by BA number."""
    conn = db_manager.connect()
    row = conn.execute("SELECT * FROM assets WHERE ba_number = ?", (ba_number,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Asset '{ba_number}' not found")
    return _row_to_asset(row)


@router.post("/", response_model=AssetResponse)
async def create_asset(asset_in: AssetCreate):
    """Creates a new asset and automatically schedules OH-I + initial service task."""
    conn = db_manager.connect()
    try:
        commission_date = asset_in.commission_date or datetime.utcnow().strftime("%Y-%m-%d")
        name = asset_in.ba_number  # Use BA number as display name

        conn.execute("""
            INSERT INTO assets (
                ba_number, name, date_of_commission,
                serial_number, asset_group, asset_type,
                commission_date, kms, total_kms,
                current_month_kms, previous_month_kms, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
        """, (
            asset_in.ba_number, name, commission_date,
            asset_in.serial_number, asset_in.asset_group, asset_in.asset_type,
            commission_date, asset_in.total_kms, asset_in.total_kms,
            asset_in.status,
        ))
        conn.commit()

        # Schedule OH-I (L04)
        lifecycle_manager.schedule_initial_overhaul(asset_in.ba_number, commission_date)

        # Seed initial maintenance task (AGT-02)
        from agents.schedule_engine import schedule_engine
        schedule_engine.seed_initial_tasks(conn, asset_in.ba_number, commission_date)

        return _row_to_asset(
            conn.execute("SELECT * FROM assets WHERE ba_number = ?", (asset_in.ba_number,)).fetchone()
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{ba_number}", response_model=AssetResponse)
async def update_asset(ba_number: str, updates: dict):
    """Updates an existing asset's fields."""
    conn = db_manager.connect()
    row = conn.execute("SELECT * FROM assets WHERE ba_number = ?", (ba_number,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Asset '{ba_number}' not found")
    # Build SET clause from provided fields (whitelist safe columns)
    allowed = {"serial_number", "asset_group", "asset_type", "status", "kms", "total_kms",
                "current_month_kms", "asset_type"}
    set_parts = []
    vals = []
    for k, v in updates.items():
        if k in allowed:
            set_parts.append(f"{k} = ?")
            vals.append(v)
    if not set_parts:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    vals.append(ba_number)
    conn.execute(f"UPDATE assets SET {', '.join(set_parts)}, updated_at = CURRENT_TIMESTAMP WHERE ba_number = ?", vals)
    conn.commit()
    return _row_to_asset(conn.execute("SELECT * FROM assets WHERE ba_number = ?", (ba_number,)).fetchone())


@router.delete("/{ba_number}")
async def delete_asset(ba_number: str):
    """
    Deletes an asset and all related records (cascade).
    GR-B05: Returns warning before deletion.
    """
    conn = db_manager.connect()
    row = conn.execute("SELECT ba_number FROM assets WHERE ba_number = ?", (ba_number,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Asset '{ba_number}' not found")

    task_count = conn.execute(
        "SELECT COUNT(*) FROM maintenance_tasks WHERE ba_number = ?", (ba_number,)
    ).fetchone()[0]
    overhaul_count = conn.execute(
        "SELECT COUNT(*) FROM overhauls WHERE ba_number = ?", (ba_number,)
    ).fetchone()[0]

    conn.execute("DELETE FROM assets WHERE ba_number = ?", (ba_number,))
    conn.commit()

    return {
        "deleted": ba_number,
        "cascade_deleted": {
            "maintenance_tasks": task_count,
            "overhauls": overhaul_count,
        },
        "warning": f"Deleted {ba_number} and {task_count + overhaul_count} related records"
    }


# ── Phase 5: POST /assets/{ba_number}/usage ───────────────────────────────────

from pydantic import BaseModel as _BM  # already imported above; alias to avoid conflict

class UsageUpdate(_BM):
    kms: float = 0.0
    hrs: float = 0.0

@router.post("/{ba_number}/usage")
async def update_usage(ba_number: str, body: UsageUpdate):
    """
    Atomically increments usage. LOGIC.md §1.6.
    current_month_kms += kms | total_meterage += kms | hrs += hrs
    """
    conn = db_manager.connect()
    if not conn.execute("SELECT 1 FROM assets WHERE ba_number = ?", (ba_number,)).fetchone():
        raise HTTPException(status_code=404, detail=f"Asset '{ba_number}' not found")

    conn.execute("""
        UPDATE assets SET
            current_month_kms = current_month_kms + ?,
            total_meterage    = total_meterage + ?,
            kms               = kms + ?,
            total_kms         = total_kms + ?,
            hrs               = hrs + ?,
            updated_at        = CURRENT_TIMESTAMP
        WHERE ba_number = ?
    """, (body.kms, body.kms, body.kms, body.kms, body.hrs, ba_number))
    conn.commit()

    r = dict(conn.execute("SELECT * FROM assets WHERE ba_number = ?", (ba_number,)).fetchone())
    return {
        "ba_number":         ba_number,
        "current_month_kms": float(r.get("current_month_kms") or 0),
        "total_meterage":    float(r.get("total_meterage") or 0),
        "kms":               float(r.get("kms") or 0),
        "hrs":               float(r.get("hrs") or 0),
    }


# ── Phase 5: POST /admin/rollover (registered via admin_router in main.py) ────

admin_router = APIRouter(prefix="/admin", tags=["Admin"])

@admin_router.post("/rollover")
async def monthly_rollover():
    """
    Monthly usage rollover in one atomic transaction. LOGIC.md §1.5.
    previous_month_kms = current_month_kms; current_month_kms = 0
    """
    conn = db_manager.connect()
    count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    conn.execute("""
        UPDATE assets SET
            previous_month_kms = current_month_kms,
            current_month_kms  = 0,
            updated_at         = CURRENT_TIMESTAMP
    """)
    conn.execute(
        "INSERT INTO agent_audit_log (agent_id, action, action_type, status) VALUES ('SYS','Monthly Rollover','rollover','success')"
    )
    conn.commit()
    return {
        "rolled_over_assets": count,
        "rollover_date": datetime.utcnow().strftime("%Y-%m-%d"),
    }
