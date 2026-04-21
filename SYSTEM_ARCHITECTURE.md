# SYSTEM_ARCHITECTURE.md
> End-to-end architecture for the Equipment Inventory & Maintenance Tracker built on the Antigravity stack.

---

## Pattern: Sidecar + RAG Pipeline

The application follows the **Sidecar Pattern**. A lightweight native shell (Tauri) manages the OS window and spawns a compiled Python backend as a sidecar process. The sidecar owns all business logic, AI inference, and data access. The frontend is a static Next.js bundle loaded locally — it never touches the internet.

```
┌─────────────────────────────────────────────────────────┐
│                     TAURI v2 SHELL                       │
│  ┌─────────────────────┐   ┌───────────────────────────┐│
│  │   Next.js 15 UI      │   │   Python Sidecar (FastAPI)││
│  │  (Static Export)     │◄──►  llama-cpp-python         ││
│  │  Tailwind + shadcn   │   │  Phi-3.5-mini GGUF        ││
│  │                      │   │  Polars LazyFrames         ││
│  │  Tabs:               │   │  LanceDB (embedded)        ││
│  │  Dashboard           │   │  nomic-embed-text-v1.5     ││
│  │  Asset Registry      │   │  Instructor + Pydantic     ││
│  │  Maintenance Mgr     │   │  SQLite                    ││
│  │  Overhaul Tracker    │   │                            ││
│  │  Conditioning        │   │  Compiled via Nuitka →     ││
│  │  Demand Forecast     │   │  standalone C++ binary     ││
│  │  Bulk Import         │   │                            ││
│  └─────────────────────┘   └───────────────────────────┘│
│                         SQLite & LanceDB on disk         │
└─────────────────────────────────────────────────────────┘
              No external network calls. Ever.
```

---

## Layer-by-Layer Breakdown

### Layer 1 — Application Shell (Tauri v2)

| Property | Detail |
|----------|--------|
| Framework | Tauri v2 (Rust-based) |
| Role | Native OS window, file system access, sidecar process management |
| Why Tauri | ~10–15 MB footprint vs Electron's ~150 MB; superior on low-spec machines |
| Distribution | Bundles everything into a single `.exe` (Windows) or `.dmg` (macOS) |
| Security | Tauri `fs` plugin with explicit allowlist for file access paths |

---

### Layer 2 — Frontend UI (Next.js 15)

| Property | Detail |
|----------|--------|
| Framework | Next.js 15+ in Static Export mode (`next export`) |
| Styling | Tailwind CSS + shadcn/ui component library |
| Served as | Local static files loaded by Tauri — no web server |
| Key screen | Mapping Review board — human-in-the-loop validation of AI field mappings |
| State | React state + TanStack Query for sidecar API calls |

**Tab structure:**
1. **Dashboard** — Alert tiles (Overdue, Critical), pie chart, bar chart
2. **Asset Registry** — Searchable table + Detail Panel (history, graphs, specs)
3. **Maintenance Manager** — Split-screen task list + Action Form
4. **Overhaul Tracker** — OH-I and OH-II sub-tabs with timeline view
5. **Conditioning** — Tyre and battery component health tracking
6. **Demand Forecast** — Fiscal Year selector + itemised supply demand
7. **Bulk Import** — Excel upload, Mapping Review board, Conflict Resolution modal

---

### Layer 3 — Backend Sidecar (Python 3.11 + FastAPI)

| Property | Detail |
|----------|--------|
| Language | Python 3.11+ |
| Framework | FastAPI — internal local REST server on `127.0.0.1` |
| Compilation | Nuitka compiles all Python + RAG logic into a standalone C++ binary |
| Data Engine | Polars with LazyFrames — memory-safe processing of large Excel workbooks |
| CORS | Restricted to `localhost` and `127.0.0.1` only |

The sidecar is the only process that touches the database, runs inference, or reads uploaded files. The frontend communicates with it exclusively through the REST API.

---

### Layer 4 — AI Inference & RAG Engine

| Component | Technology | Role |
|-----------|------------|------|
| Inference Runtime | llama-cpp-python | Runs GGUF quantised models on CPU or GPU |
| Primary Model | Microsoft Phi-3.5-mini (3.8B, 4-bit GGUF) | Reasoning engine for column-to-field mapping |
| Accuracy Enforcement | Instructor + Pydantic | Forces structured JSON output; validates field types |
| Vector Database | LanceDB (embedded) | Stores field knowledge base — no separate DB process |
| Embeddings Model | nomic-embed-text-v1.5 (sentence-transformers) | Converts headers and field descriptions into semantic vectors |

**RAG Workflow:**
```
Workbook column header
        │
        ▼
nomic-embed-text-v1.5 → vector
        │
        ▼
LanceDB semantic search → top-3 UI field candidates
        │
        ▼
Inject candidates into Phi-3.5-mini prompt as Ground Truth
        │
        ▼
Phi-3.5-mini selects best match
        │
        ▼
Instructor + Pydantic enforce JSON schema
        │
        ▼
confidence ≥ 0.75 → auto-stage  |  confidence < 0.75 → human review
```

---

### Layer 5 — Storage

| Store | Technology | Role |
|-------|------------|------|
| Relational | SQLite | All asset records, maintenance tasks, overhauls, forecasts, audit logs |
| Vector | LanceDB (embedded) | Field knowledge base for RAG; updated with confirmed mappings |
| Model files | Local disk | GGUF model + embeddings — verified by SHA-256 on startup |

---

## Agent Summary

| Agent | Trigger | Core Rule |
|-------|---------|-----------|
| ColumnMapper (AGT-01) | Excel file uploaded | Confidence < 0.75 → human review; never skip columns |
| ScheduleEngine (AGT-02) | Task marked Complete | Next due date = baseline + interval; never use actual completion date |
| ForecastAgent (AGT-03) | Fiscal Year selected | Demand = capacity formula × 1.20 buffer (hardcoded) |
| ConflictResolver (AGT-04) | BA Number collision on import | Pause pipeline; user must choose; no auto-resolve |
| StatusClassifier (AGT-05) | Every page load / task update | Recalculate live; never serve stale status |

---

## Performance & Hardware Strategy

| Optimisation | Detail |
|-------------|--------|
| Model quantisation | 4-bit GGUF — keeps peak RAM under 4 GB |
| Hardware detection | Auto-switches between CPU (AVX2/AVX512) and GPU (CUDA/Metal) |
| Memory-safe data | Polars LazyFrames prevent out-of-memory on large workbooks |
| Single binary | Tauri bundles everything — no installation required |
| Minimum spec | 4 GB RAM, dual-core CPU, no dedicated GPU needed |

---

## Security Model

| Control | Implementation |
|---------|---------------|
| Zero external calls | No outbound HTTP/DNS from any component |
| Loopback-only API | FastAPI binds to `127.0.0.1` only |
| CORS lockdown | Only `localhost` and `127.0.0.1` allowed |
| File access | Tauri `fs` allowlist — no arbitrary path access |
| SQL injection prevention | Parameterised queries only |
| Model integrity | SHA-256 checksum verification on startup |
| Air-gap ready | All models and dependencies bundled or downloaded once |

---

## Data Flow: Bulk Import (End-to-End)

```
User uploads .xlsx
      │
      ▼
Tauri passes file path to frontend
      │
      ▼
Frontend calls POST /api/v1/import/upload
      │
      ▼
Sidecar reads file with Polars LazyFrame
      │
      ▼
ColumnMapper: embed headers → LanceDB search → Phi-3.5-mini → JSON mappings
      │
      ├── confidence ≥ 0.75 → stage for import
      └── confidence < 0.75 → route to Mapping Review board (human edits)
                                        │
                                        ▼
                              User approves / corrects mappings
      │
      ▼
ConflictResolver checks each BA Number against SQLite
      │
      ├── no collision → continue
      └── collision → pause, show modal, await user choice (overwrite / keep)
      │
      ▼
POST /api/v1/import/{id}/confirm → data written to SQLite
      │
      ▼
Import summary returned to frontend
```

---

## Data Flow: Maintenance Completion (End-to-End)

```
User marks task as Complete on Maintenance Manager tab
      │
      ▼
Frontend calls POST /api/v1/maintenance/{task_id}/complete
  Body: { actual_completion_date, actual_meterage }
      │
      ▼
ScheduleEngine applies Chain Rule:
  next_due_date = previous_baseline_date + task_interval_days
  next_baseline = previous_baseline_date
      │
      ▼
New Scheduled task written to SQLite
      │
      ▼
StatusClassifier re-evaluates all tasks for this asset
      │
      ▼
Response returned: completed_task_id, next_task_id, next_due_date
      │
      ▼
Frontend refreshes Maintenance Manager — new task appears in list
```
