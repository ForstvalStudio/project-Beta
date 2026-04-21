# STATUS.md
> ⚠️ This file MUST be updated before every session ends. If the agent stops without updating this file, the project state is unknown.

---

## Current State

| Field | Value |
|-------|-------|
| **Active Phase** | Phase 2 — Data Layer |
| **Phase Status** | 🔄 IN PROGRESS |
| **Last Updated** | 2026-04-21 |
| **Last Session Summary** | SQLite, LanceDB, and Polars engines implemented in the sidecar. Wiring completed and verification script drafted. |
| **Next Action** | Run verification script and move to Phase 3 |
| **Blockers** | Awaiting dependency installation (llama-cpp-python) |

---

## Phase Completion Tracker

| Phase | Name | Status | Completed On |
|-------|------|--------|-------------|
| 0 | System Analysis | ✅ Complete | 2026-04-21 |
| 1 | Project Scaffold | ✅ Complete | 2026-04-21 |
| 2 | Data Layer | 🔄 In Progress | — |
| 3 | Core Business Logic | ⏳ Not Started | — |
| 4 | RAG Pipeline | ⏳ Not Started | — |
| 5 | FastAPI Sidecar | ⏳ Not Started | — |
| 6 | Frontend UI | ⏳ Not Started | — |
| 7 | Integration & Polish | ⏳ Not Started | — |

---

## Phase 0 Checklist Progress

| Item | Status | Notes |
|------|--------|-------|
| 0.1 Data Model Walkthrough | ✅ | schema.sql created |
| 0.2 Agent Contract Verification | ✅ | Deterministic roles identified |
| 0.3 RAG Pipeline Feasibility | ✅ | RAM/Model estimates confirmed |
| 0.4 API Surface Audit | ✅ | Endpoint logic verified |
| 0.5 Frontend Tab Inventory | ✅ | 7 tabs mapped |
| 0.6 Tauri Integration Points | ✅ | Sidecar spawn logic decided |
| 0.7 Risk Register | ✅ | Initial risks documented |
| `schema.sql` written | ✅ | Done |
| `lancedb_seed.json` written | ✅ | Done |

---

## Model Usage Log

> Track every session's model usage here to stay quota-aware.

| Session Date | Model Used | Task | Quota Impact |
|-------------|------------|------|-------------|
| _(first session)_ | — | Project docs created | Minimal |

### Model Switches This Session
_(none yet)_

### Quota Risk Flags
> List any tasks where a critical-quota model was used despite low quota.

_(none yet)_

---

## Decisions Log

> Record every non-trivial technical decision made during the build. This prevents revisiting settled questions.

| Decision | Chosen Approach | Reason | Phase |
|----------|----------------|--------|-------|
| AGT-02, 03, 04, 05 are deterministic | Pure Python functions, no SLM | Only AGT-01 needs Phi-3.5-mini; saves quota and RAM | 0 |
| Port assignment for sidecar | TBD in Phase 0.6 | Options: fixed port vs OS-assigned port 0 | 0 |

---

## Open Questions

> Questions that must be answered before the relevant phase starts.

| Question | Relevant Phase | Priority |
|----------|---------------|----------|
| What port strategy for the sidecar? Fixed vs dynamic (port 0)? | Phase 1 | High |
| Does Instructor v1.x work with llama-cpp-python's OpenAI-compat interface? | Phase 4 | High |
| What is the exact RAM usage of Phi-3.5-mini Q4_K_M on target hardware? | Phase 4 | High |
| Should LanceDB knowledge base be updated per-user or ship with a fixed seed? | Phase 4 | Medium |

---

## Known Issues / Bugs

| ID | Description | Phase Found | Status |
|----|-------------|------------|--------|
| — | No issues yet | — | — |

---

## Files Created This Project

| File | Purpose |
|------|---------|
| `SYSTEM_ARCHITECTURE.md` | Full system architecture reference |
| `AGENTS.md` | Agent contracts and conventions |
| `SPEC.md` | Source of truth — data model, business logic, features |
| `GUARDRAILS.md` | Hard constraints — what the system cannot do |
| `API_SCHEMA.md` | REST endpoint reference |
| `ANTIGRAVITY_ROLE.md` | Agent identity, conventions, session checklists |
| `MODEL_USAGE.md` | Quota tracking and model switching rules |
| `PHASE_PLAN.md` | 8-phase build plan with Phase 0 full analysis |
| `STATUS.md` | This file — live project state |

---

## How to Update This File

**At the end of every session, the agent must update:**

1. `Current State` table — update Active Phase, Last Updated, Last Session Summary, Next Action, Blockers
2. `Phase Completion Tracker` — mark any newly completed phases ✅
3. `Phase 0 Checklist Progress` (or equivalent for current phase) — tick off completed items
4. `Model Usage Log` — add a row for this session
5. `Model Switches This Session` — list any model switches made
6. `Decisions Log` — add any new decisions made
7. `Open Questions` — add new questions, mark resolved ones
8. `Known Issues` — add any bugs discovered

**Do not end a session without updating this file. This is the project's memory.**
