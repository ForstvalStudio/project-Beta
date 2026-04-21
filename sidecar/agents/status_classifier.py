"""
AGT-05 — StatusClassifier
Classifies every maintenance task by time remaining to due date.
Runs live on every query — never serves stale status (GR-B03).
"""
import logging
from datetime import date, datetime
from typing import Dict, Any

logger = logging.getLogger("sidecar.agents.status_classifier")

# Classification thresholds (days)
_THRESHOLDS = [
    (0,   "Overdue",   "#cc0000"),   # past due
    (7,   "Critical",  "#ff6600"),   # within 7 days
    (30,  "Warning",   "#ff9900"),   # within 30 days
    (90,  "Upcoming",  "#669900"),   # within 90 days
]
_DEFAULT = ("Scheduled", "#009900")  # > 90 days


class StatusClassifier:
    """
    AGT-05 — Live status evaluation agent.
    Input: due_date string (DATE or ISO format)
    Output: { task_id, status, status_colour, days_until_due }
    """

    def classify_task(self, due_date_str: str, task_id: str = "") -> Dict[str, Any]:
        """
        Classifies a single task. Returns status dict per AGENTS.md AGT-05 spec.
        days_until_due is negative for Overdue tasks.
        Completed tasks must be filtered BEFORE calling this — they are exempt.
        """
        try:
            due_dt = datetime.strptime(due_date_str[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError, AttributeError):
            logger.warning(f"Invalid due_date {due_date_str!r} for task {task_id}")
            return {
                "task_id": task_id,
                "status": "Scheduled",
                "status_colour": "#009900",
                "days_until_due": 9999,
            }

        days = (due_dt - date.today()).days  # negative = overdue

        if days < 0:
            status, colour = "Overdue", "#cc0000"
        elif days <= 7:
            status, colour = "Critical", "#ff6600"
        elif days <= 30:
            status, colour = "Warning", "#ff9900"
        elif days <= 90:
            status, colour = "Upcoming", "#669900"
        else:
            status, colour = _DEFAULT

        return {
            "task_id": task_id,
            "status": status,
            "status_colour": colour,
            "days_until_due": days,
        }

    def classify_and_update(self, task_id: str, due_date_str: str, conn) -> Dict[str, Any]:
        """
        Classifies a task and writes the live status+colour back to SQLite.
        Called by maintenance router on every GET /tasks.
        """
        result = self.classify_task(due_date_str, task_id)
        try:
            conn.execute("""
                UPDATE maintenance_tasks
                SET status = ?, status_colour = ?
                WHERE task_id = ?
            """, (result["status"], result["status_colour"], task_id))
        except Exception as e:
            logger.warning(f"Could not update status for task {task_id}: {e}")
        return result


status_classifier = StatusClassifier()
