# SPEC.md
> Source of Truth — Objective, Plan, and Structure for the Equipment Inventory & Maintenance Tracker

---

## Objective

Build a fully offline, single-binary desktop application that replaces the legacy Equipment Inventory and Maintenance Tracker. The new application preserves all existing business logic while introducing a modern UI, RAG-enhanced Excel import, and human-in-the-loop validation — deployable on low-spec Windows and macOS machines with zero internet dependency.

**Stack:** Tauri v2 + Next.js 15 + Python Sidecar (FastAPI + Nuitka) + Phi-3.5-mini GGUF + LanceDB + SQLite

---

## Data Model

### Entity: Asset

| Field | Type | Rule |
|-------|------|------|
| `ba_number` | string (PK) | Unique identifier — primary key for all records |
| `name` | string | Human-readable equipment name |
| `date_of_commission` | date | Used for age calculation and OH-I scheduling |
| `vintage_years` | computed | `(today - date_of_commission) / 365.25` |
| `kms` | float | Kilometre usage metric |
| `hrs` | float | Operating hours metric |
| `current_month_kms` | float | Temporary field — reset to 0 on 1st of each month |
| `previous_month_kms` | float | Populated from `current_month_kms` on monthly rollover |
| `total_meterage` | float | Auto-incremented whenever `current_month_kms` is updated |
| `total_capacity` | float | Used in demand forecast calculations |

### Entity: Maintenance Task

| Field | Type | Rule |
|-------|------|------|
| `task_id` | string (PK) | Auto-generated UUID |
| `ba_number` | string (FK) | Parent asset |
| `task_type` | enum | `TM-1`, `Monthly`, `Quarterly`, `Annual`, etc. |
| `task_interval_days` | int | Recurrence interval in days |
| `status` | enum | `Overdue`, `Critical`, `Warning`, `Upcoming`, `Scheduled` |
| `status_colour` | string | Hex code assigned by StatusClassifier |
| `baseline_start_date` | date | The previous task's due date — never the actual completion date |
| `due_date` | computed | `baseline_start_date + task_interval_days` |
| `actual_completion_date` | date | Set when task is marked Complete |
| `meterage_at_completion` | float | Captured at completion time |

### Entity: Overhaul

| Field | Type | Rule |
|-------|------|------|
| `overhaul_id` | string (PK) | |
| `ba_number` | string (FK) | |
| `type` | enum | `OH-I`, `OH-II`, `Discard` |
| `scheduled_date` | date | OH-I = commission + 15yr; OH-II = OH-I completion + 10yr; Discard = OH-II completion + 10yr |
| `completion_date` | date | Set on completion |

---

## Business Logic Rules

### Maintenance Chain Rule
1. Mark task as Complete → capture `actual_completion_date` and `meterage_at_completion`
2. `next_due_date = previous_baseline_date + task_interval_days`
3. `next_baseline_start_date = previous_baseline_date`
4. A new `Scheduled` task is auto-created for the same asset and type
5. **Never** base the next due date on `actual_completion_date` — prevents Schedule Drift

### Monthly Usage Rollover
- On the 1st of every month: `previous_month_kms = current_month_kms`, then `current_month_kms = 0`
- Any write to `current_month_kms` must atomically increment `total_meterage`

### Overhaul Life-Cycle
- `OH-I` scheduled date = `date_of_commission + 15 years`
- `OH-II` scheduled date = `OH-I completion_date + 10 years`
- `Discard` flag date = `OH-II completion_date + 10 years`

### Fluid Demand Forecast
```
Demand = ((Total Capacity + 10% Top-up) × Service Frequency per Year) × Asset Quantity × 1.20 Buffer
```
- `1.20` buffer is mandatory and hardcoded — accounts for leaks, spills, emergency repairs
- Fiscal Year format: `YYYY-YY`

---

## Feature Plan

### Tab 1 — Dashboard
- Alert Tiles: Overdue count and Critical count (clickable → filters Maintenance tab)
- Pie chart: distribution of maintenance task types
- Bar chart: fluid requirements summary

### Tab 2 — Asset Registry
- Searchable, sortable table of all assets
- Detail Panel: full maintenance history, usage graphs, technical specs for selected asset
- Add / Edit asset with inline validation
- Delete asset with recursive deletion warning

### Tab 3 — Maintenance Manager
- Split-screen: task list (left) + Action Form (right)
- Mark task Complete → ScheduleEngine spawns next task automatically
- Colour-coded status badges per StatusClassifier

### Tab 4 — Overhaul Tracker
- Sub-tabs for OH-I and OH-II
- Timeline view: commission → OH-I → OH-II → projected Discard

### Tab 5 — Conditioning (Tyres / Batteries)
- Component-level health tracking
- Tyre rotation intervals based on KMs
- Battery replacement tracking

### Tab 6 — Demand Forecast
- User selects Fiscal Year (YYYY-YY)
- ForecastAgent computes demand with 1.20 buffer
- Output: itemised list and chart of required supplies (Fluids, Tyres, Batteries)

### Tab 7 — Bulk Import
- Upload Excel workbook → ColumnMapper runs RAG pipeline
- Mappings below 0.75 confidence → routed to human Mapping Review board
- BA Number collision → ConflictResolver modal (user must resolve before import continues)
- Recursive Deletion warning on asset delete

---

## UI/UX Conventions

- **Dashboard-first:** App opens on the Dashboard tab
- **Human-in-the-loop:** No AI output is committed to the database without user confirmation
- **Colour system:** All status colours match the StatusClassifier spec exactly
- **Tabbed navigation:** Persistent top-level tabs, no nested routing
- **Responsive to low-spec hardware:** All tables are virtualised; Polars LazyFrames used in sidecar

---

## Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| RAM usage | Under 4 GB peak (4-bit GGUF quantisation) |
| Network | Zero external calls — fully air-gap compatible |
| Distribution | Single `.exe` (Windows) or `.dmg` (macOS) |
| Platforms | Windows 10+ (AVX2/AVX512), macOS 12+ (Metal GPU) |
| Minimum hardware | 4 GB RAM, dual-core CPU — no dedicated GPU required |
| Offline model setup | All models downloaded once on first-run setup, then bundled |
