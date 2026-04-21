# AGENTS.md
> Defines the agent's identity, role, and conventions for the Equipment Inventory & Maintenance Tracker.

---

## Agent Roster

| Agent ID | Name | Responsibility |
|----------|------|----------------|
| AGT-01 | ColumnMapper | Maps workbook column headers to UI field definitions using RAG |
| AGT-02 | ScheduleEngine | Calculates next maintenance due dates following the Chain Rule |
| AGT-03 | ForecastAgent | Computes fluid/component demand for a target Fiscal Year |
| AGT-04 | ConflictResolver | Surfaces data conflicts during bulk import and awaits human decision |
| AGT-05 | StatusClassifier | Assigns colour-coded status to maintenance tasks based on due date |

---

## AGT-01 — ColumnMapper

**Identity:** RAG-enhanced mapping agent. Maps Excel workbook column headers to target UI field definitions.

**Role:** Runs during every bulk import. Queries LanceDB for top-3 candidate UI fields per workbook column, injects them as Ground Truth into the SLM prompt, and returns structured mapping output.

**Stack:** llama-cpp-python (Phi-3.5-mini GGUF) + Instructor + Pydantic + LanceDB + nomic-embed-text-v1.5

### Input
```json
{
  "workbook_headers": ["string"],
  "lancedb_candidates": [
    {
      "workbook_col": "string",
      "top_3_matches": [
        { "ui_field": "string", "description": "string", "data_type": "string", "valid_range": "string" }
      ]
    }
  ]
}
```

### Output (Instructor-enforced)
```json
{
  "mappings": [
    {
      "workbook_col": "string",
      "ui_field": "string",
      "confidence": 0.0,
      "data_type": "string",
      "needs_review": false
    }
  ]
}
```

### Conventions
- `confidence < 0.75` → set `needs_review: true`, route to human Mapping Review board
- Every column must produce an output entry — never skip or drop a column
- `data_type` must exactly match the target UI field type (Pydantic-validated)
- After human approval, store confirmed mappings back to LanceDB to improve future accuracy

---

## AGT-02 — ScheduleEngine

**Identity:** Deterministic scheduling agent. Calculates the next maintenance task in the chain.

**Role:** Triggered when a maintenance task is marked Complete. Applies the Chain Rule to spawn the next task with the correct baseline and due date.

### Input
```json
{
  "task_id": "string",
  "actual_completion_date": "date",
  "actual_meterage": 0.0,
  "task_interval_days": 0,
  "previous_baseline_date": "date"
}
```

### Output
```json
{
  "next_task_id": "string",
  "next_baseline_start_date": "date",
  "next_due_date": "date",
  "status": "Scheduled"
}
```

### Conventions — The Chain Rule
- `next_due_date = previous_baseline_date + task_interval_days`
- `next_baseline_start_date = previous_baseline_date`
- **NEVER** use `actual_completion_date` to calculate `next_due_date` — this causes Schedule Drift
- Output is written to SQLite immediately after spawning; no buffering

---

## AGT-03 — ForecastAgent

**Identity:** Deterministic calculation agent. Computes annual supply demand for a given Fiscal Year.

**Role:** Called when a user selects a Fiscal Year on the Demand Forecast tab. Applies the fluid demand formula across all assets and returns itemised demand.

### Fluid Demand Formula
```
Demand = ((Total Capacity + 10% Top-up) × Service Frequency per Year) × Asset Quantity × 1.20 Buffer
```

### Input
```json
{
  "fiscal_year": "YYYY-YY",
  "asset_group": "string | null"
}
```

### Output
```json
{
  "fiscal_year": "string",
  "items": [
    {
      "category": "string",
      "description": "string",
      "quantity": 0.0,
      "unit": "string",
      "formula_breakdown": {
        "capacity": 0.0, "top_up": 0.0, "frequency": 0.0,
        "asset_count": 0, "buffer": 1.20, "total": 0.0
      }
    }
  ]
}
```

### Conventions
- `buffer = 1.20` is hardcoded — not configurable
- Fiscal Year format must be `YYYY-YY` (e.g. `2024-25`)
- All items include `formula_breakdown` for transparency and auditability

---

## AGT-04 — ConflictResolver

**Identity:** Import-gate agent. Pauses the import pipeline and surfaces BA Number collisions for human resolution.

**Role:** Activated when an imported Excel row contains a BA Number that already exists in SQLite. The agent must halt the pipeline and present the conflict to the user.

### Trigger Condition
```
imported_ba_number EXISTS IN assets table (SQLite)
```

### Behaviour
1. Pause import pipeline immediately — do not continue processing remaining rows
2. Surface a Conflict Resolution modal showing: existing record data vs. incoming record data
3. Present exactly two options: `"Overwrite with New Data"` or `"Keep Existing Data"`
4. Resume import only after user makes an explicit selection
5. Log resolution action to SQLite audit log

### Conventions
- No default option pre-selected
- No timeout-based auto-resolution
- Multiple conflicts in one import are presented sequentially — one per modal

---

## AGT-05 — StatusClassifier

**Identity:** Real-time status evaluation agent. Classifies every maintenance task by time remaining to due date.

**Role:** Runs on every page load and every time a task's due date or completion status changes. Assigns a status and colour code to each task.

### Classification Table

| Status | Condition | Colour |
|--------|-----------|--------|
| Overdue | Due date has passed | `#cc0000` Dark Red |
| Critical | Due within 7 days | `#ff6600` Orange-Red |
| Warning | Due within 30 days | `#ff9900` Orange |
| Upcoming | Due within 90 days | `#669900` Olive |
| Scheduled | Due in > 90 days | `#009900` Green |

### Output
```json
{
  "task_id": "string",
  "status": "Overdue | Critical | Warning | Upcoming | Scheduled",
  "status_colour": "#xxxxxx",
  "days_until_due": 0
}
```

### Conventions
- Status is always recalculated live — never served from a stale cache
- `days_until_due` is negative for Overdue tasks
- Completed tasks are exempt from classification

---

## Shared Agent Conventions

- All agents run inside the Python FastAPI sidecar — no direct frontend DOM access
- All outputs are Pydantic-validated JSON — no free-text responses
- No agent may make external API calls, DNS lookups, or outbound socket connections
- Every agent action is logged to the SQLite `agent_audit_log` table
- Agents with confidence below threshold must escalate to human review — never auto-commit uncertain outputs
