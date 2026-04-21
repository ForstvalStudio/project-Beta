from fastapi import APIRouter
from db.manager import db_manager
from agents.status_classifier import status_classifier

router = APIRouter(prefix="/stats", tags=["Statistics"])

@router.get("")
async def get_dashboard_stats():
    """
    Returns high-level statistics for the dashboard.
    All queries use named column access via sqlite3.Row factory.
    """
    conn = db_manager.connect()
    
    # 1. Total Assets
    total_assets = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    
    # 2. Serviceable (Active) Assets
    serviceable = conn.execute("SELECT COUNT(*) FROM assets WHERE status = 'Active'").fetchone()[0]
    
    # 3. Classify all pending tasks by due date (AGT-05)
    tasks = conn.execute(
        "SELECT * FROM maintenance_tasks WHERE status != 'Completed'"
    ).fetchall()
    
    upcoming = 0
    critical = 0
    overdue = 0
    warning = 0
    overdue_list = []
    
    for t in tasks:
        td = dict(t)
        due_date = td.get("due_date", "")
        if not due_date:
            continue
        classification = status_classifier.classify_task(due_date)
        task_status = classification["status"]
        if task_status == "Upcoming":
            upcoming += 1
        elif task_status == "Critical":
            critical += 1
        elif task_status == "Warning":
            warning += 1
        elif task_status == "Overdue":
            overdue += 1
            if len(overdue_list) < 2:
                overdue_list.append({
                    "id": td.get("id"),
                    "ba_number": td.get("ba_number"),
                    "description": td.get("task_description"),
                    "due_date": due_date,
                })
            
    return {
        "total_assets": total_assets,
        "serviceable": serviceable,
        "upcoming": upcoming,
        "critical": critical,
        "warning": warning,
        "overdue_tasks": overdue_list,
        "overdue_count": overdue,
        "history_data": [
            {"name": "Jan", "value": 400},
            {"name": "Feb", "value": 300},
            {"name": "Mar", "value": 600},
            {"name": "Apr", "value": 800},
            {"name": "May", "value": 500},
            {"name": "Jun", "value": 900},
        ] # Historical trend placeholder — will be live usage data in Phase 3
    }
