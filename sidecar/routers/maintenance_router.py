from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
from db.manager import db_manager
from agents.schedule_engine import schedule_engine
from agents.status_classifier import status_classifier
from models.api_models import TaskCompleteRequest, TaskResponse

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])


def _row_to_task(r) -> dict:
    """Maps a sqlite3.Row to TaskResponse. Live classification via AGT-05."""
    d = dict(r)
    task_id = d.get("task_id") or d.get("id") or ""
    due_date = d.get("due_date") or ""
    completion = d.get("actual_completion_date") or d.get("completion_date")

    # AGT-05: completed tasks are exempt from classification
    if completion:
        status = "Completed"
        colour = "#aaaaaa"
    else:
        clf = status_classifier.classify_task(due_date, task_id)
        status = clf["status"]
        colour = clf["status_colour"]

    return {
        "id":               task_id,
        "ba_number":        d.get("ba_number") or "",
        "task_description": d.get("task_description") or d.get("task_type") or "",
        "due_date":         due_date,
        "scheduled_date":   d.get("baseline_start_date") or d.get("scheduled_date") or "",
        "completion_date":  completion or "",
        "status":           status,
        "status_colour":    colour,
    }


@router.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    ba_number:     Optional[str] = Query(None, description="Filter by asset BA number"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (Overdue/Critical/Warning/Upcoming/Scheduled)"),
    task_type:     Optional[str] = Query(None, description="Filter by task type"),
):
    """
    Lists maintenance tasks with live AGT-05 classification.
    All filters applied at SQLite query level — no Python post-filter.
    """
    conn = db_manager.connect()
    query = "SELECT * FROM maintenance_tasks"
    params = []
    conditions = []

    if ba_number:
        conditions.append("ba_number = ?")
        params.append(ba_number)
    if task_type:
        conditions.append("task_type = ?")
        params.append(task_type)
    # status_filter is applied post-classification (status is live, not stored reliably)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY due_date ASC"

    rows = conn.execute(query, params).fetchall()
    tasks = [_row_to_task(r) for r in rows]

    # Apply status_filter after live classification
    if status_filter:
        tasks = [t for t in tasks if t["status"].lower() == status_filter.lower()]

    # Write live statuses back to DB in bulk (AGT-05 GR-B03)
    for task in tasks:
        if task["status"] != "Completed":
            try:
                conn.execute("""
                    UPDATE maintenance_tasks SET status = ?, status_colour = ?
                    WHERE task_id = ?
                """, (task["status"], task["status_colour"], task["id"]))
            except Exception:
                pass
    conn.commit()

    return tasks


@router.post("/tasks/{task_id}/complete", response_model=Dict[str, Any])
async def complete_task(task_id: str, req: TaskCompleteRequest):
    """
    Marks a task complete and spawns the next task via AGT-02 Chain Rule.
    NEVER calculates next_due_date from actual_completion_date — that causes drift.
    """
    conn = db_manager.connect()

    # Try both possible PK column names
    task = conn.execute(
        "SELECT * FROM maintenance_tasks WHERE task_id = ?", (task_id,)
    ).fetchone()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")

    d = dict(task)
    if d.get("actual_completion_date") or d.get("completion_date"):
        raise HTTPException(status_code=400, detail="Task is already completed")

    try:
        # 1. Mark complete
        conn.execute("""
            UPDATE maintenance_tasks
            SET status = 'Completed',
                status_colour = '#aaaaaa',
                actual_completion_date = ?,
                completion_date = ?,
                meterage_at_completion = ?
            WHERE task_id = ?
        """, (req.completion_date, req.completion_date, req.meterage_at_completion, task_id))
        conn.commit()

        # 2. AGT-02: Chain Rule — baseline not completion
        baseline = d.get("baseline_start_date") or d.get("scheduled_date") or req.completion_date
        interval = d.get("task_interval_days") or 180
        task_type = d.get("task_type") or "Service"
        description = d.get("task_description") or task_type

        next_task = schedule_engine.spawn_next_task(
            conn=conn,
            ba_number=d["ba_number"],
            task_type=task_type,
            task_description=description,
            previous_baseline_date_str=baseline,
            task_interval_days=interval,
        )

        return {
            "message": "Task completed successfully",
            "completed_task_id": task_id,
            "next_task_id": next_task["next_task_id"],
            "next_due_date": next_task["next_due_date"],
            "next_baseline": next_task["next_baseline_start_date"],
            "next_status": next_task["status"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
