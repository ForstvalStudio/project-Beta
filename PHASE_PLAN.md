# PHASE_PLAN.md
> Build plan for the Equipment Inventory & Maintenance Tracker. 8 phases, sequential. Do not start a phase until the previous one is marked ✅ COMPLETE in STATUS.md.

---

## Phase Overview

| Phase | Name | Goal | Model Tier |
|-------|------|------|------------|
| **0** | System Analysis | Understand the full system before writing a single line of code | 🟡 Sonnet / Opus |
| **1** | Project Scaffold | Tauri + Next.js + Python sidecar skeleton, folder structure, CI | 🟢 Flash / Low |
| **2** | Data Layer | SQLite schema, migrations, Polars data engine, LanceDB init | 🟡 Sonnet |
| **3** | Core Business Logic | Asset entity, maintenance Chain Rule, rollover, overhaul lifecycle | 🔴 Opus / Sonnet |
| **4** | RAG Pipeline | ColumnMapper agent, LanceDB knowledge base, embeddings, Instructor | 🔴 Opus / Sonnet |
| **5** | FastAPI Sidecar | All REST endpoints, Pydantic schemas, agent wiring, SQLite access | 🟡 Sonnet |
| **6** | Frontend UI | All 7 tabs, shadcn/ui components, TanStack Query, API service layer | 🟡 Sonnet / Low |
| **7** | Integration & Polish | Tauri shell wiring, Nuitka compilation, hardware detection, packaging | 🔴 Opus / Sonnet |

---

## ─────────────────────────────────────────
## PHASE 0 — System Analysis
## ─────────────────────────────────────────

**Status:** 🔄 IN PROGRESS
**Model:** Claude Sonnet 4.6 (Thinking) — queue if quota is critical, use Gemini Pro as fallback
**Goal:** Build a complete mental model of the entire system before writing any code. Identify all ambiguities, dependencies, and risks upfront.

### What Phase 0 Must Produce

Phase 0 is complete only when ALL of the following are answered and documented:

---

#### 0.1 — Data Model Walkthrough

Walk through every entity and verify:

- [ ] `Asset` — all fields defined, computed fields identified (`vintage_years`, `total_meterage` auto-increment logic)
- [ ] `Maintenance Task` — Chain Rule fully understood; baseline vs actual date distinction is crystal clear
- [ ] `Overhaul` — OH-I → OH-II → Discard lifecycle chain verified (15yr / 10yr / 10yr)
- [ ] `Component` (Tyre/Battery) — conditioning tracking fields defined
- [ ] `ForecastItem` — formula variables mapped to DB columns
- [ ] `ImportSession` — import pipeline state tracked in DB (upload → mapping → confirmed)
- [ ] `AgentAuditLog` — every agent action logged with timestamp, agent ID, input hash, output

Answer these before Phase 1:
- What SQLite tables are needed? List all of them.
- Which fields are computed at query time vs stored?
- What indexes are needed for the filtered queries (status, ba_number, fiscal_year)?

---

#### 0.2 — Agent Contract Verification

For each agent, verify the contract is buildable:

- [ ] **ColumnMapper (AGT-01):** Can Phi-3.5-mini (4-bit GGUF) reliably produce Instructor-enforced JSON within the 4 GB RAM limit? Confirm tokenisation approach for column header + 3-candidate prompt.
- [ ] **ScheduleEngine (AGT-02):** Fully deterministic — no SLM needed. Confirm it is a pure Python function, not an LLM call.
- [ ] **ForecastAgent (AGT-03):** Fully deterministic — no SLM needed. Confirm it is a pure Python function.
- [ ] **ConflictResolver (AGT-04):** No LLM — this is a UI flow gate. Confirm it lives in the frontend (modal) + a sidecar pause endpoint.
- [ ] **StatusClassifier (AGT-05):** Fully deterministic — no SLM needed. Confirm it runs as a Polars expression on every task query.

> Key insight from this analysis: Only AGT-01 (ColumnMapper) needs the SLM. AGT-02, 03, 04, 05 are deterministic Python. This massively reduces quota usage.

---

#### 0.3 — RAG Pipeline Feasibility Check

- [ ] Confirm `nomic-embed-text-v1.5` runs via `sentence-transformers` without a network call after first download
- [ ] Confirm LanceDB embedded mode requires no separate process
- [ ] Define the LanceDB schema for the field knowledge base:
  - `ui_field_name` (string)
  - `description` (string)
  - `data_type` (string)
  - `valid_range` (string)
  - `vector` (float array, dim=768 for nomic-embed-text-v1.5)
- [ ] Define the initial seed data for LanceDB (all UI field definitions from SPEC.md — list every field)
- [ ] Confirm Instructor v1.x works with llama-cpp-python's OpenAI-compatible interface
- [ ] Estimate prompt token count for ColumnMapper: header + 3 candidates + instruction ≈ how many tokens?

---

#### 0.4 — API Surface Audit

Walk through every endpoint in `API_SCHEMA.md` and verify:

- [ ] Every endpoint has a corresponding Pydantic request model and response model named
- [ ] Every endpoint that writes to SQLite is identified (needs a transaction)
- [ ] Every endpoint that triggers an agent is identified (needs an audit log entry)
- [ ] The import pipeline state machine is fully mapped:
  - `UPLOADED` → `MAPPING_PENDING` → `MAPPING_REVIEWED` → `CONFLICT_CHECK` → `CONFIRMED` → `COMPLETE`

---

#### 0.5 — Frontend Tab Inventory

For each of the 7 tabs, define:

- [ ] **Dashboard:** Which queries power the alert tiles? (count of tasks where status IN ('Overdue','Critical'))
- [ ] **Asset Registry:** What columns in the table? What data is in the Detail Panel?
- [ ] **Maintenance Manager:** What fields on the Action Form? What happens on "Complete"?
- [ ] **Overhaul Tracker:** What does the timeline component look like? What data does it need?
- [ ] **Conditioning:** What fields track tyre and battery health? What triggers a warning?
- [ ] **Demand Forecast:** What does the chart look like? Bar chart by category?
- [ ] **Bulk Import:** Step-by-step UI flow — Upload → Review Mappings → Resolve Conflicts → Confirm → Summary

---

#### 0.6 — Tauri Integration Points

- [ ] List every Tauri command needed (file picker, sidecar spawn, app data path)
- [ ] Define the sidecar startup sequence: Tauri spawns Python binary → FastAPI starts on random port → port communicated back to frontend
- [ ] Confirm Nuitka compilation flags for target platforms (Windows AVX2, macOS Metal)
- [ ] Define the app data directory structure:
  ```
  AppData/
  ├── db/
  │   └── tracker.sqlite
  ├── lancedb/
  │   └── knowledge_base/
  ├── models/
  │   ├── phi-3.5-mini.Q4_K_M.gguf
  │   └── nomic-embed-text-v1.5/
  └── logs/
      └── sidecar.log
  ```

---

#### 0.7 — Risk Register

Document every identified risk before Phase 1:

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Phi-3.5-mini exceeds 4 GB RAM at runtime | Medium | High | Use Q4_K_M quantisation; profile before Phase 4 |
| Nuitka compilation breaks llama-cpp-python bindings | Medium | High | Test Nuitka + llama-cpp-python in isolated env in Phase 1 |
| nomic-embed-text-v1.5 requires network on first use | Low | Medium | Pre-download and bundle in setup script |
| LanceDB concurrent write during import + query | Low | Medium | Serialise import writes behind a lock |
| Tauri port conflict for sidecar | Low | Low | Use port 0 (OS assigns) and pass to frontend via Tauri event |
| Low quota during critical Phase 3/4 logic | High | Medium | Batch complex tasks; see MODEL_USAGE.md |

---

### Phase 0 Exit Criteria

Phase 0 is **COMPLETE** only when:

- [ ] All 0.1–0.7 checklists above are fully answered
- [ ] A complete SQLite schema (all tables, columns, types, indexes) is written to `schema.sql`
- [ ] A complete LanceDB seed data file is written to `lancedb_seed.json`
- [ ] The sidecar port communication mechanism is decided
- [ ] `STATUS.md` is updated to reflect Phase 0 complete

---

## ─────────────────────────────────────────
## PHASE 1 — Project Scaffold
## ─────────────────────────────────────────

**Status:** ⏳ NOT STARTED
**Model:** Gemini 3 Flash / Gemini 3.1 Pro Low
**Goal:** Create the full folder structure, tooling config, and a "hello world" that proves Tauri + Next.js + Python sidecar can talk to each other.

### Tasks
- [ ] Init Tauri v2 project with Next.js 15 static export template
- [ ] Set up Tailwind CSS + shadcn/ui
- [ ] Create Python sidecar skeleton (FastAPI with one `/health` endpoint)
- [ ] Prove sidecar spawns from Tauri and frontend can call `/health`
- [ ] Set up Nuitka build script (stub — full compilation in Phase 7)
- [ ] Create folder structure matching the architecture doc
- [ ] Add all dependencies to `requirements.txt` and `package.json`
- [ ] Create `.env.local` and config loading pattern

### Exit Criteria
- [ ] `tauri dev` runs and shows the Next.js UI
- [ ] Frontend successfully calls `/health` on the Python sidecar
- [ ] Folder structure matches architecture

---

## ─────────────────────────────────────────
## PHASE 2 — Data Layer
## ─────────────────────────────────────────

**Status:** ⏳ NOT STARTED
**Model:** Claude Sonnet 4.6
**Goal:** All storage layers initialised and proven with seed data.

### Tasks
- [ ] Implement `schema.sql` from Phase 0 output — all tables, indexes, constraints
- [ ] Write SQLite migration runner (versioned migrations)
- [ ] Implement Polars LazyFrame Excel reader for workbook import
- [ ] Initialise LanceDB with `lancedb_seed.json` field knowledge base
- [ ] Implement `nomic-embed-text-v1.5` embedding pipeline (offline)
- [ ] Write data access layer (DAL) functions for all entities
- [ ] Seed SQLite with sample asset data for dev testing

### Exit Criteria
- [ ] All tables created with correct schema
- [ ] LanceDB knowledge base queryable with test embedding
- [ ] Sample asset readable via DAL

---

## ─────────────────────────────────────────
## PHASE 3 — Core Business Logic
## ─────────────────────────────────────────

**Status:** ⏳ NOT STARTED
**Model:** Claude Opus 4.6 (Thinking) / Sonnet
**Goal:** All deterministic business logic implemented and unit-tested.

### Tasks
- [ ] `ScheduleEngine` (AGT-02) — Chain Rule implementation with full unit tests
- [ ] `StatusClassifier` (AGT-05) — colour classification logic as Polars expression
- [ ] `ForecastAgent` (AGT-03) — fluid demand formula with hardcoded 1.20 buffer
- [ ] Monthly usage rollover logic (atomic `total_meterage` increment)
- [ ] Overhaul lifecycle auto-scheduling (OH-I → OH-II → Discard)
- [ ] Vintage age calculation
- [ ] Unit tests for every business logic rule in SPEC.md

### Exit Criteria
- [ ] All 5 Chain Rule test cases pass (including Schedule Drift prevention)
- [ ] StatusClassifier correctly classifies all 5 status levels
- [ ] Forecast formula output matches manual calculation

---

## ─────────────────────────────────────────
## PHASE 4 — RAG Pipeline
## ─────────────────────────────────────────

**Status:** ⏳ NOT STARTED
**Model:** Claude Opus 4.6 (Thinking) / Sonnet
**Goal:** ColumnMapper agent fully operational with Phi-3.5-mini + LanceDB + Instructor.

### Tasks
- [ ] Load and profile Phi-3.5-mini Q4_K_M GGUF — confirm RAM under 4 GB
- [ ] Implement `nomic-embed-text-v1.5` embedding for LanceDB queries
- [ ] Implement LanceDB top-3 semantic search for column headers
- [ ] Build Instructor + Pydantic schema for ColumnMapper output
- [ ] Implement full ColumnMapper (AGT-01) with RAG workflow
- [ ] Implement confidence threshold routing (< 0.75 → needs_review flag)
- [ ] Store confirmed mappings back to LanceDB
- [ ] Benchmark: map 20 test columns, measure accuracy and RAM

### Exit Criteria
- [ ] ColumnMapper maps 20 test columns with ≥ 85% accuracy
- [ ] RAM stays under 4 GB during inference
- [ ] All outputs are valid Pydantic-validated JSON

---

## ─────────────────────────────────────────
## PHASE 5 — FastAPI Sidecar
## ─────────────────────────────────────────

**Status:** ⏳ NOT STARTED
**Model:** Claude Sonnet 4.6
**Goal:** All REST endpoints live, wired to agents and DAL, returning correct responses.

### Tasks
- [ ] Implement all endpoints from `API_SCHEMA.md`
- [ ] Wire each endpoint to the correct agent or DAL function
- [ ] Implement import pipeline state machine
- [ ] Implement `ConflictResolver` pause/resume flow
- [ ] Add audit logging to `agent_audit_log` table
- [ ] Add SQLite transaction wrappers to all write endpoints
- [ ] Integration tests for all endpoints against a test DB

### Exit Criteria
- [ ] All API_SCHEMA.md endpoints return correct responses
- [ ] Import pipeline state machine transitions verified
- [ ] Audit log populated after every agent action

---

## ─────────────────────────────────────────
## PHASE 6 — Frontend UI
## ─────────────────────────────────────────

**Status:** ⏳ NOT STARTED
**Model:** Claude Sonnet 4.6 / Gemini 3.1 Pro Low
**Goal:** All 7 tabs built, connected to the sidecar API, human-in-the-loop flows working.

### Tasks
- [ ] API service layer (`/src/api/`) — typed wrappers for all sidecar endpoints
- [ ] TanStack Query setup with cache invalidation strategy
- [ ] Tab 1: Dashboard — alert tiles + pie chart + bar chart
- [ ] Tab 2: Asset Registry — table + Detail Panel + Add/Edit forms
- [ ] Tab 3: Maintenance Manager — split-screen + Action Form + Complete flow
- [ ] Tab 4: Overhaul Tracker — OH-I/OH-II sub-tabs + timeline
- [ ] Tab 5: Conditioning — tyre and battery health components
- [ ] Tab 6: Demand Forecast — fiscal year selector + demand chart
- [ ] Tab 7: Bulk Import — upload → Mapping Review board → Conflict Resolution modal → summary
- [ ] Colour-coded status badges matching SPEC hex codes

### Exit Criteria
- [ ] All 7 tabs render with real data from sidecar
- [ ] Mapping Review board works end-to-end
- [ ] Conflict Resolution modal blocks import correctly

---

## ─────────────────────────────────────────
## PHASE 7 — Integration & Polish
## ─────────────────────────────────────────

**Status:** ⏳ NOT STARTED
**Model:** Claude Opus 4.6 / Sonnet
**Goal:** Production-ready single binary. Everything works offline, on low-spec hardware, distributed as .exe / .dmg.

### Tasks
- [ ] Full Nuitka compilation of Python sidecar to C++ binary
- [ ] Hardware detection (CPU AVX2/AVX512 vs GPU CUDA/Metal)
- [ ] Tauri bundle config — embed sidecar binary, models, LanceDB, SQLite
- [ ] First-run setup: model download, LanceDB seed, DB migration
- [ ] Model SHA-256 checksum verification on startup
- [ ] End-to-end smoke test on a clean Windows 10 machine (4 GB RAM)
- [ ] End-to-end smoke test on macOS 12
- [ ] Final `STATUS.md` update — mark all phases complete

### Exit Criteria
- [ ] Single `.exe` runs on Windows 10 with 4 GB RAM, zero installs
- [ ] Single `.dmg` runs on macOS 12, Metal GPU auto-detected
- [ ] All GUARDRAILS.md constraints verified in production build
- [ ] `STATUS.md` shows all phases ✅ COMPLETE
