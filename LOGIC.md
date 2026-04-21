# LOGIC.md
> Complete business logic reference for the Equipment Inventory & Maintenance Tracker. Every rule here is derived from the legacy system and must be preserved exactly in the new build.

---

## 1. Core Entity: Asset

Every piece of equipment is an **Asset**. The Asset is the root entity — all maintenance, overhauls, forecasts, and conditioning records belong to an Asset.

### 1.1 Unique Identifier
- Every asset is uniquely identified by its **BA Number**
- BA Number is the primary key across all tables
- No two assets may share a BA Number — a collision during import triggers the ConflictResolver

### 1.2 Age Calculation (Vintage)
```
Vintage (years) = (Current Date − Date of Commission) / 365.25
```
- Computed at query time — not stored
- Used to determine OH-I scheduling and for display in the Asset Registry detail panel

### 1.3 Usage Metrics
Assets track usage across two independent dimensions:
- **Kilometres (KMs)** — distance-based usage
- **Operating Hours (Hrs)** — time-based usage

Both are tracked separately and used for different maintenance triggers.

### 1.4 Usage Fields
| Field | Purpose |
|-------|---------|
| `current_month_kms` | Temporary field — records activity for the current calendar month |
| `previous_month_kms` | Snapshot of last month's usage, populated on rollover |
| `total_meterage` | Running lifetime total — auto-incremented on every update to `current_month_kms` |

### 1.5 Monthly Rollover Logic
Runs automatically on the **1st of every month**:

```
Step 1: previous_month_kms = current_month_kms
Step 2: current_month_kms = 0
```

- This is atomic — both steps happen in a single transaction
- `total_meterage` is NOT reset during rollover — it is a lifetime counter

### 1.6 Auto-Update Rule
When `current_month_kms` is written to (any non-zero entry):
```
total_meterage += new_current_month_kms_value
```
- This increment is atomic with the write
- Direct writes to `total_meterage` are forbidden — it must only grow via this rule

---

## 2. Technical Maintenance (TM) Scheduling

Maintenance is a **Continuous Schedule Chain**. Completing one task automatically creates the next one. The chain never breaks.

### 2.1 The Chain Rule (Critical)

When a maintenance task is marked **Complete**:

1. Capture `actual_completion_date` and `meterage_at_completion`
2. Calculate the next task:

```
next_due_date        = previous_task.baseline_date + task_interval_days
next_baseline_date   = previous_task.baseline_date
```

3. Create a new task with status `Scheduled`

> ⚠️ **NEVER** use `actual_completion_date` to calculate `next_due_date`.
> This prevents **Schedule Drift** — where maintenance deadlines creep later and later because work is always completed slightly late.

**Example:**
```
Task due:           2024-06-01
Work done on:       2024-06-08  (7 days late)
Next due date:      2024-12-01  (baseline + 6 months)
NOT:                2024-12-08  (this would be drift)
```

### 2.2 Baseline Preservation
- The new task's `baseline_start_date` = the old task's `due_date`
- This anchors the schedule to the original cadence permanently
- No matter how late or early work is done, the schedule never moves

### 2.3 Task Status Classification

Every task is classified in real time based on the current date vs its due date:

| Status | Condition | Colour |
|--------|-----------|--------|
| **Overdue** | Due date has passed (`days_until_due < 0`) | `#cc0000` Dark Red |
| **Critical** | Due within 7 days | `#ff6600` Orange-Red |
| **Warning** | Due within 30 days | `#ff9900` Orange |
| **Upcoming** | Due within 90 days | `#669900` Olive Green |
| **Scheduled** | Due in more than 90 days | `#009900` Green |

- Status is **always recalculated live** — never served from a stale cache
- Completed tasks are exempt from classification

---

## 3. Major Life-Cycle Overhauls

Assets undergo two major factory-level overhauls during their operational life, followed by retirement.

### 3.1 Overhaul I (OH-I)
```
OH-I scheduled_date = date_of_commission + 15 years
```
- Scheduled automatically when an asset is created
- No manual scheduling — always derived from commission date

### 3.2 Overhaul II (OH-II)
```
OH-II scheduled_date = OH-I completion_date + 10 years
```
- Created automatically when OH-I is marked complete
- Based strictly on OH-I **completion date** — not the OH-I scheduled date

### 3.3 Asset Retirement (Discard)
```
Discard flag date = OH-II completion_date + 10 years
```
- Created automatically when OH-II is marked complete
- Asset enters its final 10-year operational phase after OH-II
- On the discard flag date, the asset is marked for retirement

### 3.4 Full Asset Lifecycle
```
Commission
    │
    ├── 15 years ──► OH-I Scheduled
    │                    │
    │               OH-I Completed
    │                    │
    │               + 10 years ──► OH-II Scheduled
    │                                  │
    │                             OH-II Completed
    │                                  │
    │                             + 10 years ──► Discard Flag
    │
   End of Service
```

---

## 4. Demand Forecast & Supply Chain

The system predicts logistics needs for a specific **Fiscal Year** (format: `YYYY-YY`, e.g. `2024-25`).

### 4.1 Fluid Demand Formula
```
Demand = ((Total Capacity + 10% Top-up) × Service Frequency per Year) × Asset Quantity × 1.20 Buffer
```

Breaking it down:
| Variable | Meaning |
|----------|---------|
| `Total Capacity` | The asset's fluid capacity (stored field) |
| `+ 10% Top-up` | `Total Capacity × 1.10` — accounts for topping up to full |
| `Service Frequency per Year` | How many times this fluid is serviced annually |
| `Asset Quantity` | Number of assets in scope |
| `× 1.20 Buffer` | **Mandatory safety multiplier — hardcoded, not configurable** |

### 4.2 Safety Buffer Rule
- The `1.20` multiplier accounts for leaks, spills, and emergency repairs
- It is **hardcoded** — end users cannot change it
- Any forecast output without this buffer is incorrect

### 4.3 Forecast Scope
- Forecast is always scoped to a single Fiscal Year
- Optional filter by asset group
- Output includes itemised breakdown: Fluids, Tyres, Batteries

---

## 5. Data Import Logic

### 5.1 Bulk Import Flow
```
Upload Excel file
      ↓
ColumnMapper maps headers to UI fields (RAG pipeline)
      ↓
Confidence ≥ 0.75 → staged for import
Confidence < 0.75 → flagged for human review on Mapping Review board
      ↓
Human approves / corrects all flagged mappings
      ↓
BA Number collision check against SQLite
      ↓
Collision found → ConflictResolver modal
  → User chooses: "Overwrite with New Data" OR "Keep Existing Data"
  → No default, no timeout, no auto-resolve
      ↓
User confirms → data written to SQLite
```

### 5.2 Conflict Resolution Rules
- Import **pauses** at any BA Number collision
- User must make an **explicit choice** — no default option pre-selected
- Multiple conflicts in one import are presented **sequentially**
- Resolution action is logged to the audit log

### 5.3 Recursive Deletion Rule
When a user deletes an asset:
- System must display a warning listing all child records that will be removed:
  - Maintenance tasks
  - Overhaul records
  - Forecast records
  - Conditioning records
- User must explicitly confirm — not just dismiss the modal
- All deletion happens in a single transaction — partial deletion is not allowed

---

## 6. Interface Logic Rules

### 6.1 Dashboard Alert Tiles
- Alert tiles show counts of **Overdue** and **Critical** tasks
- Clicking a tile navigates to the Maintenance Manager tab with that status filter pre-applied
- Counts are live — refreshed on every dashboard load

### 6.2 Maintenance Manager Split-Screen
- Left panel: task list filtered by status/asset
- Right panel: Action Form — edit or complete the selected task
- Completing a task on the Action Form triggers the Chain Rule immediately
- The task list refreshes after completion to show the newly spawned task

### 6.3 Overhaul Tracker Timeline
- Shows: Commission Date → OH-I Scheduled → OH-I Completed → OH-II Scheduled → OH-II Completed → Discard Flag
- Dates that are in the future are shown as projected
- Dates that have passed are shown as completed

### 6.4 Conditioning (Tyres / Batteries)
- Tracks component-level health independently per asset
- Tyre rotation intervals are based on **KMs** (not time)
- Battery replacement tracking uses its own interval logic
- Component warnings use the same status colour system as maintenance tasks

### 6.5 Demand Forecast Display
- User selects a Fiscal Year from a dropdown
- ForecastAgent computes demand and returns itemised results
- Results displayed as both a table and a bar chart (by category: Fluids, Tyres, Batteries)
- Each row includes the full formula breakdown for transparency

---

## 7. Logic Invariants

These are truths that must hold at all times in the system. If any of these is violated, there is a bug:

| # | Invariant |
|---|-----------|
| L1 | Every asset has exactly one OH-I record (auto-created on asset creation) |
| L2 | OH-II is created if and only if OH-I is marked complete |
| L3 | Discard flag is created if and only if OH-II is marked complete |
| L4 | Every completed maintenance task has exactly one successor task in `Scheduled` status |
| L5 | `total_meterage` is always ≥ the sum of all `previous_month_kms` values |
| L6 | No task's `next_due_date` equals `actual_completion_date + interval` (Schedule Drift check) |
| L7 | No import completes with an unresolved BA Number collision |
| L8 | Every ColumnMapper output entry has a `needs_review` field — no column is silently skipped |
| L9 | The forecast `buffer` field in every output row equals exactly `1.20` |
| L10 | No asset deletion occurs without a confirmed recursive deletion warning |
