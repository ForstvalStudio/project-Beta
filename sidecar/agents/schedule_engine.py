"""
AGT-02 — ScheduleEngine
Deterministic scheduling agent. Enforces the Chain Rule.
next_due_date = previous_baseline_date + task_interval_days
NEVER uses actual_completion_date — that causes Schedule Drift.
"""
import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger("sidecar.agents.schedule_engine")


class ScheduleEngine:
    """
    AGT-02 — Chain Rule implementation.
    next_due_date      = previous_baseline_date + task_interval_days
    next_baseline_date = previous_baseline_date  (NOT completion date)
    """

    def spawn_next_task(
        self,
        conn,
        ba_number: str,
        task_type: str,
        task_description: str,
        previous_baseline_date_str: str,
        task_interval_days: int,
    ) -> Dict[str, Any]:
        """
        Spawns the next task in the chain. Writes to SQLite immediately.

        Chain Rule (GR-B02 / AGT-02):
          next_baseline_start_date = previous_baseline_date
          next_due_date            = previous_baseline_date + interval

        Returns the new task dict.
        """
        try:
            baseline = datetime.strptime(previous_baseline_date_str[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            logger.error(f"Invalid baseline date: {previous_baseline_date_str!r}")
            raise ValueError(f"Invalid baseline_start_date: {previous_baseline_date_str!r}")

        next_baseline = baseline                                  # CHAIN RULE
        next_due_date = baseline + timedelta(days=task_interval_days)  # CHAIN RULE

        # Classify new task immediately (AGT-05)
        from agents.status_classifier import status_classifier
        classification = status_classifier.classify_task(next_due_date.strftime("%Y-%m-%d"))
        status = classification["status"]
        status_colour = classification["status_colour"]

        task_id = f"TSK-{ba_number}-{task_type}-{uuid.uuid4().hex[:6].upper()}"

        conn.execute("""
            INSERT INTO maintenance_tasks (
                task_id, ba_number, task_type, task_description,
                task_interval_days, status, status_colour,
                baseline_start_date, due_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id, ba_number, task_type, task_description,
            task_interval_days, status, status_colour,
            next_baseline.strftime("%Y-%m-%d"),
            next_due_date.strftime("%Y-%m-%d"),
        ))
        conn.commit()

        logger.info(
            f"[AGT-02] Spawned {task_id} for {ba_number}: "
            f"baseline={next_baseline}, due={next_due_date}, status={status}"
        )

        return {
            "next_task_id": task_id,
            "next_baseline_start_date": next_baseline.strftime("%Y-%m-%d"),
            "next_due_date": next_due_date.strftime("%Y-%m-%d"),
            "status": status,
            "status_colour": status_colour,
        }

    def seed_initial_tasks(
        self, 
        conn, 
        ba_number: str, 
        commission_date_str: str,
        is_hrs_only: bool = False
    ):
        """
        Seeds the initial maintenance schedule for a newly imported asset.
        Creates one Scheduled task starting from commission date.
        Called by import_router after successful INSERT.
        
        For HRS-only assets (Gen set, JCB, Dozer, SSL), uses hours-based intervals.
        """
        try:
            baseline = datetime.strptime(commission_date_str[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            logger.warning(f"Cannot seed tasks for {ba_number} — invalid date: {commission_date_str!r}")
            return

        # For HRS-only assets, use hours-based intervals
        # Days are still stored, but interval is shorter for HRS equipment
        if is_hrs_only:
            interval = 90  # 3 months for HRS-only equipment
            task_type = "Service-HRS"
            description = f"{task_type} — {interval} day cycle (HRS-based maintenance)"
        else:
            interval = 180  # Standard 180-day service interval
            task_type = "Service"
            description = f"{task_type} — {interval} day cycle"
        
        due_date = baseline + timedelta(days=interval)

        from agents.status_classifier import status_classifier
        classification = status_classifier.classify_task(due_date.strftime("%Y-%m-%d"))

        task_id = f"TSK-{ba_number}-SVC-INIT"

        # Idempotent: skip if already exists
        existing = conn.execute(
            "SELECT task_id FROM maintenance_tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        if existing:
            return

        conn.execute("""
            INSERT INTO maintenance_tasks (
                task_id, ba_number, task_type, task_description,
                task_interval_days, status, status_colour,
                baseline_start_date, due_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id, ba_number, task_type, description,
            interval,
            classification["status"], classification["status_colour"],
            baseline.strftime("%Y-%m-%d"),
            due_date.strftime("%Y-%m-%d"),
        ))
        conn.commit()
        logger.info(f"[AGT-02] Seeded initial task {task_id} for {ba_number}, due {due_date} " +
                   f"(HRS-only={is_hrs_only})")


schedule_engine = ScheduleEngine()
