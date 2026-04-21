# GUARDRAILS.md
> Defines what the system and agents cannot do. Every rule here is a hard constraint — not a guideline.

---

## Data Integrity Guardrails

### GR-D01 — No Schedule Drift
> **FORBIDDEN:** Using `actual_completion_date` to calculate the next maintenance due date.

- Next due date **must** be: `previous_baseline_date + task_interval_days`
- The baseline is always the old task's scheduled due date — regardless of when work was done
- Violating this causes maintenance deadlines to drift progressively later over time

---

### GR-D02 — No Silent Conflict Resolution
> **FORBIDDEN:** Auto-merging or auto-overwriting records on a BA Number collision.

- Import pipeline must **pause** at any BA Number collision
- User must explicitly choose `"Overwrite with New Data"` or `"Keep Existing Data"` before the import resumes
- No default option pre-selected; no timeout-based auto-resolve

---

### GR-D03 — No Silent Deletion
> **FORBIDDEN:** Deleting an asset without showing a recursive deletion warning.

- Deletion must display a confirmation modal listing all child records that will be removed (maintenance tasks, overhauls, forecasts)
- User must make an explicit confirmation — not just dismiss the modal

---

### GR-D04 — No Direct Total Meterage Writes
> **FORBIDDEN:** Overwriting `total_meterage` directly without going through `current_month_kms`.

- Any entry to `current_month_kms` must atomically increment `total_meterage`
- On the 1st of each month: `previous_month_kms = current_month_kms`, then `current_month_kms = 0`

---

## AI Agent Guardrails

### GR-A01 — No External Network Calls
> **FORBIDDEN:** Any agent, module, or library making outbound HTTP, DNS, or socket calls.

- All inference must use locally bundled GGUF model files via `llama-cpp-python`
- All embeddings must use the locally bundled `nomic-embed-text-v1.5` model
- CORS and firewall must block all non-localhost traffic at both the Tauri and FastAPI layers

---

### GR-A02 — No Auto-Commit on Low-Confidence Mapping
> **FORBIDDEN:** Committing a column mapping with `confidence < 0.75`.

- Mappings below 0.75 must be routed to the human Mapping Review board
- User must explicitly approve or correct the mapping before data is written to SQLite
- Agent may suggest but must never decide unilaterally on uncertain mappings

---

### GR-A03 — No Free-Text Agent Output
> **FORBIDDEN:** Any agent returning unstructured free-text as its primary output.

- All agent outputs must conform to Pydantic-validated JSON schemas
- Instructor enforces schema compliance before output is consumed downstream
- If the model cannot produce valid JSON, the operation must fail with a structured error — not return raw text

---

### GR-A04 — No Column Skipping
> **FORBIDDEN:** Silently ignoring or dropping unmapped workbook columns.

- Every column in the uploaded workbook must produce an output entry
- Unmapped columns are flagged for review — they are never silently dropped

---

## Business Logic Guardrails

### GR-B01 — Forecast Buffer is Non-Negotiable
> **FORBIDDEN:** Computing demand forecast without the `1.20` safety buffer multiplier.

- `buffer = 1.20` is hardcoded — it must not be exposed as a user-configurable setting
- The `10%` top-up on Total Capacity is also mandatory in the fluid demand formula
- These values protect against leaks, spills, and emergency repairs

---

### GR-B02 — Overhaul & Discard Scheduling
> **FORBIDDEN:** Scheduling OH-II based on any date other than the OH-I Completion Date.
> **FORBIDDEN:** Scheduling the Discard flag based on any date other than the OH-II Completion Date.

- `OH-II scheduled_date = OH-I completion_date + 10 years`
- `Discard flag date = OH-II completion_date + 10 years`
- Using commission date or any other date for these calculations is incorrect

---

### GR-B03 — No Stale Status Display
> **FORBIDDEN:** Displaying a maintenance task without a freshly evaluated colour-coded status.

- Status must be recalculated on every page load and every time a task's due date or completion state changes
- Stale cached statuses must never be rendered to the user
- Completed tasks are exempt from status classification

---

## Security Guardrails

### GR-S01 — Localhost-Only API
> **FORBIDDEN:** The FastAPI sidecar accepting connections from any address other than `127.0.0.1`.

- CORS must be restricted to `http://localhost` and `http://127.0.0.1` only

---

### GR-S02 — No SQL Injection
> **FORBIDDEN:** Constructing SQL queries by string concatenation with user-provided data.

- All database queries must use parameterised statements via the ORM or `?` placeholders

---

### GR-S03 — Sandboxed File Access
> **FORBIDDEN:** Accessing arbitrary file paths outside Tauri's allowlisted file system scope.

- All file read/write must go through Tauri's `fs` plugin APIs with an explicit allowlist
- The Python sidecar may only access paths passed to it by Tauri — not resolve arbitrary paths

---

### GR-S04 — Model Integrity Verification
> **FORBIDDEN:** Loading a GGUF or embedding model file without verifying its checksum.

- On startup, all model files must be verified against known SHA-256 checksums
- Checksum mismatch must abort startup and alert the user — not silently load the modified file
