from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from datetime import datetime
from db.manager import db_manager
from agents.schedule_engine import schedule_engine
from agents.status_classifier import status_classifier
from models.api_models import TaskCompleteRequest, TaskResponse

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])

@router.get("/tasks", response_model=List[TaskResponse])
async def list_tasks():
    """
    Lists all maintenance tasks with real-time status evaluation (AGT-05).
    """
    conn = db_manager.connect()
    rows = conn.execute("SELECT * FROM maintenance_tasks").fetchall()
    
    tasks = []
    for r in rows:
        # AGT-05: Live status classification
        status_info = status_classifier.classify_task(r[3]) # r[3] is due_date
        
        tasks.append({
            "id": r[0],
            "ba_number": r[1],
            "task_description": r[2],
            "due_date": r[3],
            "scheduled_date": r[4],
            "completion_date": r[5],
            "status": status_info["status"],
            "status_colour": status_info["status_colour"]
        })
    return tasks

@router.post("/tasks/{task_id}/complete", response_model=Dict[str, Any])
async def complete_task(task_id: str, req: TaskCompleteRequest):
    """
    Marks a task as complete and spawns the next task in the chain (AGT-02).
    Enforces the Chain Rule (Zero Schedule Drift).
    """
    conn = db_manager.connect()
    task = conn.execute("SELECT * FROM maintenance_tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 1. Update current task
    try:
        with conn:
            conn.execute("""
                UPDATE maintenance_tasks 
                SET status = 'Completed', 
                    completion_date = ?, 
                    meterage_at_completion = ?
                WHERE id = ?
            """, (req.completion_date, req.meterage_at_completion, task_id))
            
            # TODO: Pull actual interval and description from a 'task_types' table in the future.
            # For now, we assume standard 180 day cycle for 'Service' tasks.
            interval = 180 
            
            # 2. Trigger AGT-02: Calculate next task with DRIFT PREVENTION
            # task[4] is the previous_baseline (scheduled_date)
            next_task = schedule_engine.calculate_next_task(
                task[2], # description
                task[4], # previous_baseline
                interval
            )
            
            # 3. Insert next task
            new_id = f"TSK-{int(datetime.now().timestamp())}"
            conn.execute("""
                INSERT INTO maintenance_tasks (id, ba_number, task_description, due_date, scheduled_date, status)
                VALUES (?, ?, ?, ?, ?, 'Scheduled')
            """, (new_id, task[1], task[2], next_task["next_due_date"], next_task["next_baseline_start_date"]))

        return {
            "message": "Task completed successfully",
            "next_task_id": new_id,
            "next_due_date": next_task["next_due_date"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
