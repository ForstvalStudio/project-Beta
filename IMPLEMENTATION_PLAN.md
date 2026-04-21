# IMPLEMENTATION_PLAN.md
> Live implementation tracker. Update this file as each item is completed.
> Last updated: Phase 2 in progress.

---

## Current System Health

| Layer | Status | Notes |
|-------|--------|-------|
| Tauri Shell | ⏳ Pending | Wired in Phase 7 |
| Next.js Frontend | 🔄 In Progress | Pages render, data partially wired |
| FastAPI Sidecar | ✅ Stable | All routes registered, syntax clean |
| SQLite Schema | ✅ Fixed | schema.sql synced to live DB structure |
| LanceDB Knowledge Base | ✅ Working | ui_fields table seeded and queryable |
| AGT-01 ColumnMapper | ✅ Working | Maps 6 headers, logs to audit table |
| AGT-02 ScheduleEngine | ✅ Built | Chain Rule, seeds tasks on import |
| AGT-03 ForecastAgent | ✅ Built | 1.20 buffer, per-group demand |
| AGT-04 ConflictResolver | ⏳ Phase 5 | Skip-on-duplicate implemented |
| AGT-05 StatusClassifier | ✅ Built | Live classification, 5 thresholds |
| Import Pipeline | ✅ Working | imported=3, skipped=0 confirmed |
| WebSocket | ✅ Stable | Ref-based hook, StrictMode safe |

---

## Phase 0 — System Analysis ✅ COMPLETE

All outputs produced and committed to repo root.

| Output | Status |
|--------|--------|
| schema.sql | ✅ Committed |
| lancedb_seed.json | ✅ Committed |
| All 11 .md reference docs | ✅ Committed |
| Risk register documented | ✅ In PHASE_PLAN.md |
| Sidecar port strategy decided | ✅ Fixed port 8000 |

---

## Phase 1 — Project Scaffold ✅ COMPLETE

| Task | Status | Notes |
|------|--------|-------|
| Tauri + Next.js skeleton | ✅ | Running on localhost:3000 |
| Python FastAPI sidecar | ✅ | Running on 127.0.0.1:8000 |
| Frontend calls /health | ✅ | Confirmed |
| Offline embedding model | ✅ | HF network calls eliminated |
| Embedding singleton | ✅ | Loads once at startup |
| Llama singleton | ✅ | Phi-3.5-mini loads at boot |
| Auth routes removed | ✅ | GR-S01 satisfied |
| Lifespan handler | ✅ | on_event deprecation fixed |
| AGT-01 ColumnMapper | ✅ | Maps headers, no Instructor |
| Audit log schema | ✅ | action column fixed |
| Self-healing schema sync | ✅ | Covers all tables |

---

## Phase 2 — Data Layer & Import Flow 🔄 IN PROGRESS

### 2A — Schema Cleanup (BLOCKING everything else)

| Task | Status | Fix Required |
|------|--------|-------------|
| Remove duplicate `commission_date` column | ❌ | Keep `date_of_commission` only |
| Remove duplicate `total_kms` column | ❌ | Keep `kms` only |
| One-time migration to move data across | ❌ | SQLite recreate-table pattern |
| schema.sql updated to match | ❌ | Single source of truth |

---

### 2B — Import Confirmation Pipeline (CRITICAL PATH)

| Task | Status | Notes |
|------|--------|-------|
| `POST /api/v1/import/{id}/confirm` route exists | ✅ | Route registered |
| Confirm endpoint actually writes to SQLite | ✅ | imported=3 skipped=0 confirmed |
| Log skip reason per row | ✅ | Full INFO logging per row |
| Only require ba_number as mandatory field | ✅ | Implemented |
| Fallback: use ba_number as name if name missing | ✅ | Implemented |
| Accept both Commission Date and commission_date | ✅ | FIELD_TO_COLUMNS handles both |
| Auto-create OH-I on asset insert | ✅ | lifecycle_manager.schedule_initial_overhaul |
| Seed initial maintenance task on import | ✅ | schedule_engine.seed_initial_tasks |
| Return `{ imported: int, skipped: int, errors: [] }` | ✅ | Correct counts |

---

### 2C — Asset CRUD Endpoints

| Task | Status | Notes |
|------|--------|-------|
| `GET /api/v1/assets/` returns real SQLite data | ✅ | Named column access, fallbacks |
| `GET /api/v1/assets/{ba_number}` detail view | ✅ | Returns full asset |
| `POST /api/v1/assets/` creates single asset | ✅ | Seeds OH-I + initial task |
| `PUT /api/v1/assets/{ba_number}` update | ✅ | Whitelist-safe update |
| `DELETE /api/v1/assets/{ba_number}` with recursive warning | ✅ | Returns cascade count |
| Search/filter query param on GET /assets/ | ✅ | ?search= param live |

---

### 2D — Stats Endpoint

| Task | Status | Notes |
|------|--------|-------|
| `GET /api/v1/stats` returns real counts | ✅ | Returns real SQLite counts |
| total_assets from SQLite count | ✅ | |
| overdue_tasks count | ✅ | via AGT-05 |
| critical_tasks count | ✅ | via AGT-05 |
| upcoming_tasks count | ✅ | via AGT-05 |

---

### 2E — WebSocket Stability

| Task | Status | Notes |
|------|--------|-------|
| Single WebSocket per app session | ❌ | Currently opens per page nav |
| SidecarProvider context in layout.tsx | ❌ | Not built |
| Only /import page sends messages | ❌ | |
| Other pages read connection status from context | ❌ | |
| Sidecar keeps connection open after mapping | ❌ | Closes after each job |

---

### 2F — Frontend Data Wiring

| Task | Status | Notes |
|------|--------|-------|
| Asset Registry table shows real data | ❌ | Shows empty |
| Dashboard alert tiles show real counts | ❌ | Shows zeros |
| Import confirm button calls confirm endpoint | ⚠️ | Calls but gets skipped=3 |
| After confirm — redirect to Asset Registry | ❌ | |
| Empty state: "No assets yet — import to get started" | ❌ | |

---

## Phase 3 — Core Business Logic ⏳ NOT STARTED

### 3A — AGT-02 ScheduleEngine

| Task | Status | Notes |
|------|--------|-------|
| Chain Rule implementation | ✅ | spawn_next_task() in schedule_engine.py |
| next_due_date = baseline + interval (never actual completion date) | ✅ | Enforced |
| Auto-spawn next task on completion | ✅ | POST /maintenance/tasks/{id}/complete |
| Seed initial tasks on import | ✅ | seed_initial_tasks() called on import |
| `POST /maintenance/{task_id}/complete` wired to ScheduleEngine | ✅ | |

---

### 3B — AGT-05 StatusClassifier

| Task | Status | Notes |
|------|--------|-------|
| Overdue: days_until_due < 0 -> #cc0000 | ✅ | |
| Critical: due within 7 days -> #ff6600 | ✅ | |
| Warning: due within 30 days -> #ff9900 | ✅ | |
| Upcoming: due within 90 days -> #669900 | ✅ | |
| Scheduled: due > 90 days -> #009900 | ✅ | |
| Runs on every GET /maintenance/tasks query | ✅ | Writes live status back to DB |
| Never serves stale status (GR-B03) | ✅ | |

---

### 3C — AGT-03 ForecastAgent

| Task | Status | Notes |
|------|--------|-------|
| Fluid demand formula implemented | ✅ | forecast_agent.py |
| 1.20 buffer hardcoded (GR-B01) | ✅ | _BUFFER = 1.20 |
| 10% top-up on capacity | ✅ | _TOP_UP_RATE = 0.10 |
| Fiscal year scoping (YYYY-YY format) | ✅ | Validated |
| `GET /api/v1/forecast/` wired to ForecastAgent | ✅ | |
| Returns formula_breakdown per item | ✅ | |

---

### 3D — AGT-04 ConflictResolver

| Task | Status | Notes |
|------|--------|-------|
| BA Number collision detection on import | ❌ | |
| Import pauses on collision (GR-D02) | ❌ | |
| Frontend Conflict Resolution modal | ❌ | |
| Two options: Overwrite / Keep Existing | ❌ | |
| No default selection (GR-D02) | ❌ | |
| Resume import after user resolves | ❌ | |

---

### 3E — Overhaul Lifecycle

| Task | Status | Notes |
|------|--------|-------|
| OH-I auto-created on asset insert (commission + 15yr) | ❌ | LOGIC.md 3.1 |
| OH-II auto-created on OH-I completion (+ 10yr) | ❌ | LOGIC.md 3.2 |
| Discard flag auto-created on OH-II completion (+ 10yr) | ❌ | LOGIC.md 3.3 |
| `GET /api/v1/overhauls` endpoint | ❌ | |
| `PUT /api/v1/overhauls/{id}/complete` endpoint | ❌ | |

---

### 3F — Monthly Usage Rollover

| Task | Status | Notes |
|------|--------|-------|
| current_month_kms write atomically increments total_meterage | ❌ | LOGIC.md 1.6 |
| 1st of month rollover: current → previous, reset to 0 | ❌ | LOGIC.md 1.5 |
| `POST /assets/{ba_number}/usage` endpoint | ❌ | |
| `POST /admin/rollover` manual trigger endpoint | ❌ | |

---

## Phase 4 — RAG Pipeline Optimisation ⏳ NOT STARTED

| Task | Status | Notes |
|------|--------|-------|
| Batch all headers into ONE LLM call | ❌ | Currently 6 calls = slow |
| Single prompt returns full JSON array | ❌ | |
| n_threads = os.cpu_count() // 2 | ❌ | |
| n_batch = 512 in Llama constructor | ❌ | |
| Benchmark: measure time before and after | ❌ | |
| Confirmed mappings saved back to LanceDB | ❌ | Improves future accuracy |

---

## Phase 5 — Full API Surface ⏳ NOT STARTED

| Endpoint | Status | Notes |
|----------|--------|-------|
| `DELETE /api/v1/assets/{ba_number}` | ❌ | With recursive deletion warning |
| `PUT /api/v1/assets/{ba_number}` | ❌ | Partial update supported |
| `GET /api/v1/maintenance/tasks` with filters | ❌ | status, ba_number, task_type params |
| `GET /api/v1/overhauls` | ❌ | |
| `PUT /api/v1/overhauls/{id}/complete` | ❌ | |
| `POST /api/v1/assets/{ba_number}/usage` | ❌ | |
| `POST /api/v1/admin/rollover` | ❌ | |
| All endpoints return correct error schema | ❌ | Per API_SCHEMA.md |

---

## Phase 6 — Frontend UI Completion ⏳ NOT STARTED

| Tab | Status | Blocking On |
|-----|--------|-------------|
| Dashboard — alert tiles with real counts | ❌ | StatusClassifier (Phase 3) |
| Dashboard — pie chart maintenance types | ❌ | Real task data |
| Dashboard — bar chart fluid requirements | ❌ | ForecastAgent (Phase 3) |
| Asset Registry — searchable table | ❌ | Import fix (Phase 2) |
| Asset Registry — Detail Panel | ❌ | GET /assets/{ba_number} |
| Asset Registry — Add/Edit forms | ❌ | POST/PUT endpoints |
| Asset Registry — Delete with warning | ❌ | DELETE endpoint |
| Maintenance Manager — split screen | ❌ | AGT-02 (Phase 3) |
| Maintenance Manager — Complete flow | ❌ | ScheduleEngine |
| Maintenance Manager — colour badges | ❌ | AGT-05 (Phase 3) |
| Overhaul Tracker — OH-I/OH-II sub-tabs | ❌ | Phase 3 |
| Overhaul Tracker — timeline view | ❌ | Phase 3 |
| Conditioning — tyre/battery tracking | ❌ | Phase 3 |
| Demand Forecast — fiscal year selector | ❌ | ForecastAgent (Phase 3) |
| Demand Forecast — demand chart | ❌ | ForecastAgent (Phase 3) |
| Bulk Import — Mapping Review board | ⚠️ | Partially working |
| Bulk Import — Conflict Resolution modal | ❌ | AGT-04 (Phase 3) |
| Bulk Import — confirmation + redirect | ❌ | Import fix (Phase 2) |
| Chart container size fix (width=-1 warning) | ❌ | Quick fix |

---

## Phase 7 — Integration & Distribution ⏳ NOT STARTED

| Task | Status | Notes |
|------|--------|-------|
| Tauri shell wiring — sidecar spawn | ❌ | |
| Tauri shell wiring — file system APIs | ❌ | |
| Port communication Tauri → frontend | ❌ | |
| Nuitka compilation of Python sidecar | ❌ | |
| Hardware detection CPU/GPU auto-switch | ❌ | |
| First-run setup: model download + DB init | ❌ | |
| SHA-256 model checksum verification | ❌ | GR-S04 |
| Tauri bundle config — embed all assets | ❌ | |
| Smoke test: Windows 10 4GB RAM clean machine | ❌ | |
| Smoke test: macOS 12 Metal GPU | ❌ | |

---

## Known Issues (Active)

| ID | Issue | Severity | Phase |
|----|-------|----------|-------|
| BUG-02 | Duplicate columns commission_date + total_kms in assets table | Medium | Resolved — schema.sql synced, code uses canonical names |
| BUG-04 | Chart width=-1 height=-1 warning on Dashboard | Low | 6 |
| BUG-05 | AGT-01 makes 6 LLM calls instead of 1 batched call | Medium | 4 |

---

## Resolved Issues

| ID | Issue | Resolved In |
|----|-------|-------------|
| FIX-01 | HuggingFace network calls on every startup (GR-A01 violation) | Phase 1 |
| FIX-02 | Instructor .choices attribute crash on llama-cpp-python dict | Phase 1 |
| FIX-03 | JWT auth routes present (GR-S01 violation) | Phase 1 |
| FIX-04 | on_event deprecation warning | Phase 1 |
| FIX-05 | agent_audit_log action column NOT NULL failure | Phase 1 |
| FIX-06 | Embedding model reloading on every mapping request | Phase 1 |
| FIX-07 | Llama model loading on first request instead of startup | Phase 1 |

---

## Logic Invariants Verification Status

These 10 invariants from LOGIC.md must all pass before Phase 7:

| # | Invariant | Status |
|---|-----------|--------|
| L1 | Every asset has exactly one OH-I record | ❌ Not verified |
| L2 | OH-II created only when OH-I complete | ❌ Not built |
| L3 | Discard created only when OH-II complete | ❌ Not built |
| L4 | Every completed task has one successor Scheduled task | ❌ Not built |
| L5 | total_meterage ≥ sum of all previous_month_kms | ❌ Not built |
| L6 | No task next_due_date = actual_completion + interval | ❌ Not built |
| L7 | No import completes with unresolved BA collision | ❌ Not built |
| L8 | Every ColumnMapper output has needs_review field | ✅ Implemented |
| L9 | Every forecast buffer = exactly 1.20 | ❌ Not built |
| L10 | No asset deletion without recursive warning | ❌ Not built |

---

## Next 3 Actions (Priority Order)

1. **Fix BUG-02** — Remove duplicate columns from schema.sql and run migration
2. **Fix BUG-01** — Make confirm endpoint write assets to SQLite (imported > 0)
3. **Fix BUG-03** — Move WebSocket to SidecarProvider context in layout.tsx
