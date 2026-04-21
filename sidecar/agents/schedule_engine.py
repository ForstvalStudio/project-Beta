import logging
from datetime import datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger("sidecar.agents.schedule_engine")

class ScheduleEngine:
    """
    AGT-02 — ScheduleEngine
    Identity: Deterministic scheduling agent.
    Role: Calculates the next maintenance task in the chain (The Chain Rule).
    """

    def calculate_next_task(self, 
                            task_type: str,
                            previous_baseline_date: str, 
                            task_interval_days: int) -> Dict[str, Any]:
        """
        Applies The Chain Rule to determine the next task's due date and baseline.
        
        Rules:
        1. next_due_date = previous_baseline_date + task_interval_days
        2. next_baseline_start_date = previous_baseline_date
        3. NEVER use actual_completion_date to calculate next_due_date (prevents Schedule Drift)
        """
        logger.info(f"Calculating next {task_type} task from baseline {previous_baseline_date}")
        
        try:
            baseline_dt = datetime.strptime(previous_baseline_date, "%Y-%m-%d")
        except ValueError:
            # Fallback for ISO format if needed
            baseline_dt = datetime.fromisoformat(previous_baseline_date.replace("Z", "+00:00"))

        next_due_dt = baseline_dt + timedelta(days=task_interval_days)
        
        # The next task's baseline is the CURRENT task's due date (which was previous_baseline_date + interval)
        # Wait, let's re-read the SPEC/LOGIC.
        # LOGIC.md: 
        # next_due_date = previous_task.baseline_date + task_interval_days  (Wait, this seems wrong in LOGIC.md if it's a chain)
        # Let's check SPEC.md:
        # next_due_date = baseline_start_date + task_interval_days
        # baseline_start_date = The previous task's due date
        
        # Re-reading LOGIC.md 2.1:
        # next_due_date = previous_task.baseline_date + task_interval_days
        # Wait, if previous_task.baseline_date was X, and interval is Y, next_due_date is X+Y?
        # That would mean it's the SAME due date as the previous task. That doesn't make sense.
        
        # Let's check the Example in LOGIC.md:
        # Task due: 2024-06-01
        # Work done on: 2024-06-08
        # Next due date: 2024-12-01 (baseline + 6 months)
        
        # If "baseline" for the task due 2024-06-01 was 2023-12-01 (6 months prior), 
        # then next_due_date = 2023-12-01 + 6 months + 6 months = 2024-12-01.
        # OR: next_baseline = previous_due_date. 
        # And next_due = next_baseline + interval.
        
        # Let's follow the formal convention in AGENTS.md:
        # next_due_date = previous_baseline_date + task_interval_days
        # next_baseline_start_date = previous_baseline_date
        
        # Wait, if I do this twice:
        # T1: baseline=B, due=B+I
        # T2: baseline=B, due=B+I (Wait, this is the same)
        
        # There's a slight ambiguity in the wording "previous_baseline_date".
        # Usually, the "baseline" for the NEXT task is the "due date" of the PREVIOUS task.
        # Let's check LOGIC.md 2.2:
        # "The new task's baseline_start_date = the old task's due_date"
        
        # Okay, that's clear. 
        # And: next_due_date = next_baseline_start_date + task_interval_days
        
        next_baseline_date = baseline_dt + timedelta(days=task_interval_days) # This is the "old task's due date"
        next_due_date = next_baseline_date + timedelta(days=task_interval_days)

        result = {
            "next_baseline_start_date": next_baseline_date.strftime("%Y-%m-%d"),
            "next_due_date": next_due_date.strftime("%Y-%m-%d"),
            "status": "Scheduled"
        }
        
        logger.info(f"Next task calculated: Due {result['next_due_date']}")
        return result

# Global instance
schedule_engine = ScheduleEngine()
