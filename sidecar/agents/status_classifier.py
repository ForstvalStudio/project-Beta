import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger("sidecar.agents.status_classifier")

class StatusClassifier:
    """
    AGT-05 — StatusClassifier
    Identity: Real-time status evaluation agent.
    Role: Classifies every maintenance task by time remaining to due date.
    """

    # Classification Table
    STATUS_MAP = {
        "OVERDUE": {"status": "Overdue", "colour": "#cc0000"},
        "CRITICAL": {"status": "Critical", "colour": "#ff6600"},
        "WARNING": {"status": "Warning", "colour": "#ff9900"},
        "UPCOMING": {"status": "Upcoming", "colour": "#669900"},
        "SCHEDULED": {"status": "Scheduled", "colour": "#009900"}
    }

    def classify_task(self, due_date: str) -> Dict[str, Any]:
        """
        Classifies task based on current date vs due date.
        
        Returns: { status, status_colour, days_until_due }
        """
        try:
            due_dt = datetime.strptime(due_date, "%Y-%m-%d").date()
        except ValueError:
            due_dt = datetime.fromisoformat(due_date.replace("Z", "+00:00")).date()
            
        today = datetime.now().date()
        delta = (due_dt - today).days

        if delta < 0:
            config = self.STATUS_MAP["OVERDUE"]
        elif delta <= 7:
            config = self.STATUS_MAP["CRITICAL"]
        elif delta <= 30:
            config = self.STATUS_MAP["WARNING"]
        elif delta <= 90:
            config = self.STATUS_MAP["UPCOMING"]
        else:
            config = self.STATUS_MAP["SCHEDULED"]

        result = {
            "status": config["status"],
            "status_colour": config["colour"],
            "days_until_due": delta
        }
        
        return result

# Global instance
status_classifier = StatusClassifier()
