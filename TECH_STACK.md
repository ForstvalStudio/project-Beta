# TECH_STACK.md
> Canonical reference for every technology used in the Equipment Inventory & Maintenance Tracker. No library or tool may be added to the project without being listed here first.

---

## Stack Overview

```
┌─────────────────────────────────────────────────────────────┐
│  DISTRIBUTION: Single .exe (Windows) / .dmg (macOS)         │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  TAURI v2 (Rust)  ←  Application Shell               │   │
│  │                                                      │   │
│  │  ┌─────────────────┐    ┌────────────────────────┐   │   │
│  │  │  Next.js 15      │    │  Python 3.11 Sidecar   │   │   │
│  │  │  Static Export   │◄──►│  FastAPI               │   │   │
│  │  │  Tailwind CSS    │    │  Polars LazyFrames      │   │   │
│  │  │  shadcn/ui       │    │  llama-cpp-python       │   │   │
│  │  │  TanStack Query  │    │  Phi-3.5-mini GGUF      │   │   │
│  │  └─────────────────┘    │  Instructor + Pydantic   │   │   │
│  │                         │  LanceDB (embedded)      │   │   │
│  │                         │  nomic-embed-text-v1.5   │   │   │
│  │                         │  SQLite                  │   │   │
│  │                         │  ── compiled via Nuitka ─│   │   │
│  │                         └────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────┘   │
│                    100% Offline. Zero external calls.        │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1 — Application Shell

### Tauri v2
| Property | Detail |
|----------|--------|
| Language | Rust |
| Version | v2.x (latest stable) |
| Role | Native OS window, file system access, spawns Python sidecar process |
| Why | ~10–15 MB footprint vs Electron's ~150 MB; superior performance on low-spec machines |
| Key APIs used | `tauri::shell` (sidecar), `tauri-plugin-fs` (file access with allowlist), Tauri events (port handoff) |
| Distribution | Bundles entire app into a single `.exe` (Windows) or `.dmg` (macOS) |
| Platforms | Windows 10+ (AVX2/AVX512), macOS 12+ (Metal) |

---

## Layer 2 — Frontend UI

### Next.js 15+
| Property | Detail |
|----------|--------|
| Version | 15+ |
| Mode | Static Export (`next export`) — no server, loaded as local files by Tauri |
| Language | TypeScript (strict mode, no `any`) |
| Role | All 7 application tabs, Mapping Review board, Conflict Resolution modal |
| Routing | App Router (Next.js 13+ convention) |

### Tailwind CSS
| Property | Detail |
|----------|--------|
| Role | Utility-first styling for all components |
| Config | Custom colour tokens matching SPEC status hex codes (`#cc0000`, `#ff6600`, `#ff9900`, `#669900`, `#009900`) |

### shadcn/ui
| Property | Detail |
|----------|--------|
| Role | Pre-built accessible component library (tables, modals, forms, tabs, charts) |
| Rule | Only shadcn/ui components — no additional UI libraries without updating this file |

### TanStack Query
| Property | Detail |
|----------|--------|
| Role | Async data fetching, caching, and cache invalidation for all sidecar API calls |
| Rule | All sidecar calls go through typed wrappers in `/src/api/` — no raw `fetch` in components |

---

## Layer 3 — Backend Sidecar

### Python 3.11+
| Property | Detail |
|----------|--------|
| Version | 3.11+ (use `match` statements, `tomllib`, `ExceptionGroup` where appropriate) |
| Role | All business logic, agent orchestration, data processing, REST API |

### FastAPI
| Property | Detail |
|----------|--------|
| Role | Internal local REST server — listens on `127.0.0.1` only |
| CORS | Restricted to `http://localhost` and `http://127.0.0.1` |
| Validation | All request/response bodies use Pydantic v2 models |
| Docs | `/docs` disabled in production build |

### Nuitka
| Property | Detail |
|----------|--------|
| Role | Compiles the entire Python sidecar (FastAPI + agents + RAG + data engine) into a standalone C++ binary |
| Output | Single portable executable — no Python runtime required on end-user machine |
| Phase | Compiled in Phase 7 (Integration & Polish) |

### Polars
| Property | Detail |
|----------|--------|
| Role | Memory-efficient data processing for Excel workbook import |
| Mode | LazyFrames — deferred execution prevents OOM on large workbooks |
| Rule | **Never use pandas** — Polars only throughout the entire sidecar |

---

## Layer 4 — AI Inference & RAG Engine

### llama-cpp-python
| Property | Detail |
|----------|--------|
| Role | Runs GGUF quantised models locally — OpenAI-compatible interface |
| Backend | Auto-detects CPU (AVX2/AVX512) or GPU (CUDA/Metal) at runtime |
| Rule | All inference is local — zero external API calls |

### Microsoft Phi-3.5-mini (3.8B)
| Property | Detail |
|----------|--------|
| Format | GGUF — `phi-3.5-mini.Q4_K_M.gguf` (4-bit quantisation) |
| Role | Reasoning engine for ColumnMapper (AGT-01) — selects best field match from RAG context |
| RAM target | Under 4 GB peak with Q4_K_M quantisation |
| Used by | AGT-01 only — all other agents are deterministic Python |

### Instructor
| Property | Detail |
|----------|--------|
| Version | v1.x |
| Role | Forces Phi-3.5-mini to return structured JSON conforming to Pydantic schemas |
| Interface | Uses llama-cpp-python's OpenAI-compatible completion endpoint |
| Rule | All SLM outputs must pass Instructor validation before being consumed |

### Pydantic v2
| Property | Detail |
|----------|--------|
| Role | Schema definition and validation for all agent inputs/outputs and FastAPI models |
| Rule | Every agent output is a Pydantic model — no unvalidated dicts passed between layers |

### nomic-embed-text-v1.5
| Property | Detail |
|----------|--------|
| Library | `sentence-transformers` (local, offline after first download) |
| Dimensions | 768-dimensional vectors |
| Role | Converts workbook column headers and UI field descriptions into vectors for semantic search |
| Rule | Must run fully offline — bundled or pre-downloaded before distribution |

### LanceDB (Embedded)
| Property | Detail |
|----------|--------|
| Mode | Embedded — no separate database process |
| Role | Stores the field knowledge base: UI field names, descriptions, data types, valid ranges, vectors |
| Seeded with | All UI field definitions from SPEC.md (`lancedb_seed.json` created in Phase 0) |
| Updated with | Confirmed column mappings after human approval — improves future accuracy |
| Schema | `ui_field_name` (str), `description` (str), `data_type` (str), `valid_range` (str), `vector` (float[768]) |

---

## Layer 5 — Storage

### SQLite
| Property | Detail |
|----------|--------|
| Role | All persistent relational data — assets, maintenance tasks, overhauls, forecasts, audit logs, import sessions |
| Access | Via parameterised queries only — no f-string or string-concatenated SQL |
| Location | `{AppData}/db/tracker.sqlite` |
| Migrations | Versioned migration runner initialised in Phase 2 |

---

## App Data Directory Structure

```
{AppData}/
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

## Performance Targets

| Metric | Target |
|--------|--------|
| Peak RAM usage | < 4 GB (4-bit GGUF + LazyFrames) |
| Cold start time | < 10 seconds on minimum-spec hardware |
| Minimum CPU | Dual-core with AVX2 support |
| Minimum RAM | 4 GB |
| GPU | Optional — CUDA (Windows) or Metal (macOS) auto-detected |
| Distribution size | Target < 2 GB including bundled models |

---

## Dependency Rules

- ✅ Add a new dependency → update this file first, then `requirements.txt` / `package.json`, then note in `PHASE_PLAN.md` phase notes
- ❌ No CDN imports — all JS/CSS must be local or bundled
- ❌ No external API calls from any layer, ever
- ❌ No `pandas` — Polars only
- ❌ No additional UI libraries beyond shadcn/ui without explicit approval in this file
