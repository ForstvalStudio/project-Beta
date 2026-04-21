from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime, date
from db.manager import db_manager
from logic.lifecycle import lifecycle_manager

router = APIRouter(prefix="/overhauls", tags=["Overhauls"])


def _row_to_overhaul(r) -> dict:
    d = dict(r)
    # Calculate days until due (for scheduled overhauls)
    days_until = None
    sched = d.get("scheduled_date")
    if sched and not d.get("completion_date"):
        try:
            due_dt = datetime.strptime(sched[:10], "%Y-%m-%d").date()
            days_until = (due_dt - date.today()).days
        except (ValueError, TypeError):
            pass

    return {
        "overhaul_id":      d.get("overhaul_id") or "",
        "ba_number":        d.get("ba_number") or "",
        "type":             d.get("type") or d.get("overhaul_type") or "OH-I",
        "scheduled_date":   sched or "",
        "completion_date":  d.get("completion_date") or "",
        "status":           d.get("status") or "Scheduled",
        "days_until_due":   days_until,
    }


class OverhaulCompleteRequest(BaseModel):
    completion_date: str
    meterage: float = 0.0


@router.get("/")
async def list_overhauls(
    ba_number:  Optional[str] = Query(None),
    type:       Optional[str] = Query(None, description="OH-I, OH-II, Discard"),
    status:     Optional[str] = Query(None, description="Scheduled, Completed"),
):
    """Returns all overhaul records with optional filters."""
    conn = db_manager.connect()
    conditions = []
    params = []

    if ba_number:
        conditions.append("ba_number = ?")
        params.append(ba_number)
    if type:
        conditions.append("(type = ? OR overhaul_type = ?)")
        params.extend([type, type])
    if status:
        conditions.append("status = ?")
        params.append(status)

    query = "SELECT * FROM overhauls"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY scheduled_date ASC"

    rows = conn.execute(query, params).fetchall()
    return [_row_to_overhaul(r) for r in rows]


@router.put("/{overhaul_id}/complete")
async def complete_overhaul(overhaul_id: str, req: OverhaulCompleteRequest) -> Dict[str, Any]:
    """
    Marks overhaul complete and spawns next lifecycle stage.
    OH-I → OH-II (+10yr). OH-II → Discard (+10yr).  LOGIC.md §3.2/3.3.
    """
    conn = db_manager.connect()
    row = conn.execute(
        "SELECT * FROM overhauls WHERE overhaul_id = ?", (overhaul_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Overhaul '{overhaul_id}' not found")

    d = dict(row)
    if d.get("completion_date"):
        raise HTTPException(status_code=400, detail="Overhaul is already completed")

    completed_type = d.get("type") or d.get("overhaul_type") or "OH-I"
    ba_number = d["ba_number"]

    # Mark complete
    conn.execute("""
        UPDATE overhauls SET status = 'Completed', completion_date = ?
        WHERE overhaul_id = ?
    """, (req.completion_date, overhaul_id))
    conn.commit()

    # Spawn next lifecycle stage
    next_id = None
    next_type = None
    next_date = None

    if completed_type in ("OH-I", "OH-II"):
        lifecycle_manager.schedule_next_overhaul(ba_number, completed_type, req.completion_date)
        # Fetch the newly created record
        type_map = {"OH-I": "OH-II", "OH-II": "DISCARD"}
        next_type = type_map[completed_type]
        id_map = {"OH-I": f"OHL-{ba_number}-OH2", "OH-II": f"OHL-{ba_number}-DSC"}
        next_id = id_map[completed_type]
        # Get scheduled date
        next_row = conn.execute(
            "SELECT scheduled_date FROM overhauls WHERE overhaul_id = ?", (next_id,)
        ).fetchone()
        if next_row:
            next_date = dict(next_row).get("scheduled_date")

    return {
        "completed_overhaul_id": overhaul_id,
        "completed_type":        completed_type,
        "next_overhaul_id":      next_id,
        "next_type":             next_type,
        "next_scheduled_date":   next_date,
    }
