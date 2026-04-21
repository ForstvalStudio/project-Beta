from fastapi import APIRouter, Query
from typing import Optional
from db.manager import db_manager
from agents.status_classifier import status_classifier
from agents.forecast_agent import forecast_agent

router = APIRouter(prefix="/stats", tags=["Statistics"])


@router.get("")
async def get_dashboard_stats():
    """
    Returns real-time dashboard statistics from SQLite.
    AGT-05 classifies tasks live — no stale cache.
    """
    conn = db_manager.connect()

    # ── Asset counts ──────────────────────────────────────────────────────────
    total_assets   = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    active_assets  = conn.execute("SELECT COUNT(*) FROM assets WHERE status = 'Active'").fetchone()[0]

    # ── Task classification (AGT-05 live) ─────────────────────────────────────
    pending_tasks = conn.execute("""
        SELECT * FROM maintenance_tasks
        WHERE actual_completion_date IS NULL AND completion_date IS NULL
    """).fetchall()

    overdue  = 0
    critical = 0
    warning  = 0
    upcoming = 0
    scheduled = 0
    overdue_list = []

    for t in pending_tasks:
        d = dict(t)
        task_id  = d.get("task_id") or ""
        due_date = d.get("due_date") or ""
        clf = status_classifier.classify_task(due_date, task_id)
        s = clf["status"]

        if s == "Overdue":
            overdue += 1
            if len(overdue_list) < 5:
                overdue_list.append({
                    "id": task_id,
                    "ba_number": d.get("ba_number"),
                    "description": d.get("task_description") or d.get("task_type"),
                    "due_date": due_date,
                    "days_overdue": abs(clf["days_until_due"]),
                })
        elif s == "Critical":
            critical += 1
        elif s == "Warning":
            warning += 1
        elif s == "Upcoming":
            upcoming += 1
        else:
            scheduled += 1

    # ── Overhaul counts ───────────────────────────────────────────────────────
    pending_overhauls = conn.execute(
        "SELECT COUNT(*) FROM overhauls WHERE status != 'Completed'"
    ).fetchone()[0]

    # ── Monthly usage trend (last 6 months synthetic from kms data) ──────────
    # Real trend will come from usage log in Phase 5
    top_assets = conn.execute(
        "SELECT ba_number, kms FROM assets ORDER BY kms DESC LIMIT 6"
    ).fetchall()
    history_data = [
        {"name": dict(a)["ba_number"], "value": float(dict(a)["kms"] or 0)}
        for a in top_assets
    ] or [
        {"name": "No Data", "value": 0}
    ]

    return {
        "total_assets":       total_assets,
        "active_assets":      active_assets,
        "pending_overhauls":  pending_overhauls,
        "tasks": {
            "overdue":   overdue,
            "critical":  critical,
            "warning":   warning,
            "upcoming":  upcoming,
            "scheduled": scheduled,
            "total":     len(pending_tasks),
        },
        "overdue_tasks":      overdue_list,
        # Legacy flat fields (frontend may read these)
        "overdue_count":      overdue,
        "critical":           critical,
        "warning":            warning,
        "upcoming":           upcoming,
        "serviceable":        active_assets,
        "history_data":       history_data,
    }


@router.get("/forecast")
async def get_forecast(
    fiscal_year: str = Query(..., description="Fiscal year in YYYY-YY format"),
    asset_group: Optional[str] = Query(None)
):
    """AGT-03 ForecastAgent demand calculation."""
    try:
        result = forecast_agent.compute(fiscal_year, asset_group)
        return result
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
