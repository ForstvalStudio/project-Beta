# STATUS.md
> ⚠️ This file MUST be updated before every session ends. If the agent stops without updating this file, the project state is unknown.

---

## Current State

| Field | Value |
|-------|-------|
| **Active Phase** | Phase 7 — Integration & Distribution |
| **Phase Status** | 🔄 IN PROGRESS |
| **Last Updated** | 2026-04-22 |
| **Last Session Summary** | **CODE GENERATION SYSTEM IMPLEMENTED (AGT-CODE)**:
- **AGT-CODE**: LLM writes Python classifier function from sample headers
- **EXECUTE**: Runs generated Python code at native speed (0.1ms per header)
- **CACHE**: Stores generated classifiers by header fingerprint
- **FALLBACK**: LLM only for unknown headers (0-5 headers, not 40+)
- **Expected Speedup**: 101s → 12s first sheet, 3s cached sheets
- **Pattern Recognition**: BA NO, KM RUN, HRS RUN, ENG OIL, etc.
- **Fallback**: Batch mode if code gen fails |
| **Next Action** | Restart server, test 161_f import — verify 30-60 second completion |
| **Blockers** | None |

---

## Phase Completion Tracker

| Phase | Name | Status | Completed On |
|-------|------|--------|-------------|
| 0 | System Analysis | ✅ Complete | 2026-04-21 |
| 1 | Project Scaffold | ✅ Complete | 2026-04-21 |
| 2 | Data Flow & Import | ✅ Complete | 2026-04-22 |
| 3 | Core Business Logic | ✅ Complete | 2026-04-22 |
| 4 | RAG Pipeline Optimisation | ✅ Complete | 2026-04-22 |
| 5 | Full API Surface | ✅ Complete | 2026-04-22 |
| 6 | Frontend UI Wiring | ✅ Complete | 2026-04-22 |
| 7 | Integration & Distribution | 🔄 In Progress | — |

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
| 2026-04-22 | Claude Sonnet 4.6 (Thinking) | AI schema discovery pipeline implementation | High |

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
| Port assignment for sidecar | Fixed port 8000 on 127.0.0.1 | Loopback binding IS the security model (GR-S01) | 1 |
| No authentication layer | Zero JWT/auth middleware | GR-S01: loopback binding is the security model | 2 |
| Model singleton pattern | Both Nomic-Embed and Phi-3.5-mini loaded once at boot | Prevents per-request init latency; eliminates HF network calls | 2 |
| No hardcoded FIELD_TO_COLUMNS | AI schema discovery at runtime | Column structure varies per workbook; dynamic discovery required | 7 |
| openpyxl for Excel reading | Replaced Polars with openpyxl | Merged multi-row headers require cell-by-cell parsing | 7 |
| Equipment type overhaul rules | Asset group determines OH-I trigger | MTL 30yr, ALS 9yr, Gen set/JCB/Dozer/SSL 8yr, etc. | 7 |
| HRS-only asset handling | 90-day intervals for HRS equipment | Gen set, JCB, Dozer, SSL have no KMS tracking | 7 |

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
| KI-001 | Auth routes (`/api/v1/auth/*`) existed in codebase — GR-S01 violation | Phase 2 | ✅ Resolved — auth_router.py deleted, Depends removed from all routers |
| KI-002 | Embedding model made ~40 HF network requests on every load — GR-A01 violation | Phase 2 | ✅ Resolved — `HF_HUB_OFFLINE=1`, singleton pattern, dynamic snapshot path |
| KI-003 | `@app.on_event("startup")` deprecation warning from FastAPI | Phase 2 | ✅ Resolved — replaced with `asynccontextmanager lifespan` handler |
| KI-004 | `google.generativeai` FutureWarning from instructor import | Phase 2 | ✅ Resolved — suppressed via `warnings.filterwarnings` in main.py |
| KI-005 | Phi-3.5-mini initialized on first WS request (slow UX) | Phase 2 | ✅ Resolved — `get_column_mapper_client()` called at sidecar boot |
| KI-006 | `apiFetch` threw immediately when sidecar unreachable — no retry, blank page | Phase 2 | ✅ Resolved — retry wrapper (5×2s) in `api/index.ts` |
| KI-007 | WebSocket showed `[object Event]` on error, no reconnect logic | Phase 2 | ✅ Resolved — auto-reconnect (5×3s), `sidecar_unavailable` state in `useSidecar.ts` |
| KI-008 | Recharts `width(-1) height(-1)` — charts rendered before container measured | Phase 2 | ✅ Resolved — `ResponsiveContainer` given explicit pixel `height` inside `minHeight` div |
| KI-009 | `ColumnMapper` crashed with `'dict' object has no attribute 'choices'` — Instructor incompatible with llama-cpp-python dict response | Phase 2 | ✅ Resolved — Instructor removed entirely; direct `response["choices"][0]["message"]["content"]` + manual JSON parsing |
| KI-010 | `agent_audit_log` missing `action_type`, `input_hash`, `output_preview` columns — INSERT failed silently | Phase 2 | ✅ Resolved — schema.sql updated, self-healing sync adds missing columns on next startup |
| KI-011 | `NOT NULL constraint failed: agent_audit_log.action` — old table had column `action`, code writes `action_type` | Phase 2 | ✅ Resolved — structural migration in `run_initial_migration` drops and recreates table if old schema detected |
| KI-012 | Live DB had both `action` (NOT NULL) and `action_type` columns — INSERT only wrote `action_type`, leaving `action` empty | Phase 2 | ✅ Resolved — INSERT now writes `action_type` to both columns |
| KI-013 | WebSocket retry loop on Dashboard — `useSidecar` opened WS on all pages, retried forever | Phase 2 | ✅ Resolved — added `enabled` param; WS only opens when `enabled=true` (Import page only) |
| KI-014 | `imported=0, skipped=3` — legacy `name TEXT NOT NULL` + `date_of_commission DATE NOT NULL` caused every INSERT to fail silently | Phase 2 | ✅ Resolved — import_router writes both old+new columns, ba_number used as fallback name, per-row skip logging |
| KI-015 | WS opens multiple connections on Import page — circular `connect⇔scheduleReconnect` useCallback deps + React StrictMode double-mount | Phase 2 | ✅ Resolved — all WS state in refs, zero-dep `connect()`, `isConnectingRef` guard |

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
