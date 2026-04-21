from fastapi import APIRouter, Depends
from db.manager import db_manager
from logic.auth import get_current_user
from agents.status_classifier import status_classifier

router = APIRouter(prefix="/stats", tags=["Statistics"])

@router.get("")
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    """
    Returns high-level statistics for the dashboard.
    """
    conn = db_manager.connect()
    
    # 1. Total Assets
    total_assets = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    
    # 2. Serviceable (Active) Assets
    serviceable = conn.execute("SELECT COUNT(*) FROM assets WHERE status = 'Active'").fetchone()[0]
    
    # 3. Tasks distribution (requires live classification for accuracy, but we can query by stored due_date)
    # For performance, we'll query all pending tasks and classify them in memory 
    # (since we expect < 10,000 tasks, this is fast with Python)
    tasks = conn.execute("SELECT due_date FROM maintenance_tasks WHERE status != 'Completed'").fetchall()
    
    upcoming = 0
    critical = 0
    overdue = 0
    overdue_list = []
    
    for t in tasks:
        classification = status_classifier.classify_task(t[0])
        status = classification["status"]
        if status == "Upcoming":
            upcoming += 1
        elif status == "Critical":
            critical += 1
        elif status == "Overdue":
            overdue += 1
            if len(overdue_list) < 2:
                # Need to fetch task details for the list
                task_detail = conn.execute("SELECT id, ba_number, task_description, due_date FROM maintenance_tasks WHERE due_date = ?", (t[0],)).fetchone()
                if task_detail:
                    overdue_list.append({
                        "id": task_detail[0],
                        "ba_number": task_detail[1],
                        "description": task_detail[2],
                        "due_date": task_detail[3]
                    })
            
    return {
        "total_assets": total_assets,
        "serviceable": serviceable,
        "upcoming": upcoming,
        "critical": critical,
        "warning": len(tasks) - (upcoming + critical + overdue),
        "overdue_tasks": overdue_list,
        "history_data": [
            {"name": "Jan", "value": 400},
            {"name": "Feb", "value": 300},
            {"name": "Mar", "value": 600},
            {"name": "Apr", "value": 800},
            {"name": "May", "value": 500},
            {"name": "Jun", "value": 900},
        ] # Hardcoded for now, would be usage trends in production
    }
