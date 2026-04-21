# MODEL_USAGE.md
> Controls which AI model the agent uses based on available quota. Read this before any inference-heavy task.

---

## Available Models & Current Quota Status

> ⚠️ Update the STATUS column below at the start of every session based on your quota dashboard.

| Model | Tier | Best For | Quota Status | Refreshes |
|-------|------|----------|--------------|-----------|
| Claude Opus 4.6 (Thinking) | 🔴 Premium | Complex architecture, cross-file reasoning, debugging hard logic | **LOW** | ~3 days, 10 hrs |
| Claude Sonnet 4.6 (Thinking) | 🟡 Standard | Most coding tasks, refactoring, agent logic | **LOW** | ~3 days, 10 hrs |
| Gemini 3.1 Pro (High) | 🟡 Standard | Large context, full-file reads, documentation | **LOW** | ~2 days, 19 hrs |
| Gemini 3.1 Pro (Low) | 🟢 Economy | Simple edits, boilerplate, small functions | **LOW** | ~2 days, 19 hrs |
| Gemini 3 Flash | 🟢 Economy | Fast lookups, formatting, trivial completions | **AVAILABLE** | ~5 hrs |
| GPT-OSS 120B (Medium) | 🟢 Economy | General code, fallback for all tasks | **LOW** | ~3 days, 10 hrs |

---

## Model Selection Rules

### Rule 1 — Match Task Complexity to Model Tier

| Task Type | Preferred Model | Fallback |
|-----------|----------------|---------|
| Full system design, cross-layer architecture decisions | Claude Opus 4.6 (Thinking) | Claude Sonnet 4.6 (Thinking) |
| Agent logic, RAG pipeline, Pydantic schemas | Claude Sonnet 4.6 (Thinking) | Gemini 3.1 Pro (High) |
| FastAPI route handlers, SQLite queries | Claude Sonnet 4.6 (Thinking) | Gemini 3.1 Pro (High) |
| Next.js components, Tailwind UI | Gemini 3.1 Pro (High) | Gemini 3.1 Pro (Low) |
| Boilerplate, config files, simple functions | Gemini 3.1 Pro (Low) | Gemini 3 Flash |
| Documentation edits, status updates | Gemini 3 Flash | GPT-OSS 120B (Medium) |
| Trivial formatting, renaming, small fixes | Gemini 3 Flash | Gemini 3 Flash |

---

### Rule 2 — Quota Warning Thresholds

When a model's quota bar is at or below these levels, treat it as the indicated status:

| Bar Level (visual estimate) | Status | Action |
|-----------------------------|--------|--------|
| > 60% remaining | ✅ Free to use | Use normally |
| 30–60% remaining | 🟡 Caution | Use only for tasks that require this tier |
| 10–30% remaining | 🟠 Low | Prefer fallback; use this model only if fallback cannot do the job |
| < 10% remaining | 🔴 Critical | Do NOT use — route all tasks to fallback immediately |
| 0% / exhausted | ⛔ Exhausted | Blocked until refresh — check refresh time |

---

### Rule 3 — Current Quota Situation (from screenshot)

Based on the current quota screenshot, **all premium and standard models are LOW**. Apply the following routing until quotas refresh:

```
ALL TASKS → Gemini 3 Flash (primary)
           → GPT-OSS 120B Medium (secondary fallback)

EXCEPTION: Tasks that strictly require reasoning/thinking (agent logic, chain rule impl, 
           RAG pipeline) → queue for Claude Sonnet 4.6 after refresh in ~3 days, 10 hrs
```

> 📌 **Do not burn remaining Claude or Gemini Pro quota on boilerplate, config, or documentation tasks.**
> Save remaining premium quota for Phase 0 analysis and Phase 1 critical logic only.

---

### Rule 4 — Model Switching Protocol

When the agent detects it is about to use a low/critical quota model for a non-critical task:

1. **STOP** — do not proceed with the expensive model
2. Check if the task can be downgraded to a lower tier model
3. If yes → switch and note the switch in `STATUS.md` under "Model Switches This Session"
4. If no (task genuinely requires the tier) → log it as a "Quota Risk" in `STATUS.md` and proceed with minimal token usage
5. Never silently use a critical-quota model — always log it

---

## Quota-Aware Task Batching

To preserve quota across phases, batch similar tasks:

- **Batch documentation edits** — run all `.md` file updates in one Gemini Flash session
- **Batch boilerplate generation** — generate all config files, `__init__.py`, folder structures in one low-tier session
- **Reserve thinking models** for: agent contract implementation, Chain Rule logic, RAG pipeline, Pydantic schema design, and debugging non-obvious errors
- **Never use a thinking model** for: renaming variables, formatting code, writing comments, updating status files

---

## Refresh Schedule (as of last screenshot)

| Model Group | Refreshes In |
|-------------|-------------|
| Claude Sonnet 4.6 + Opus 4.6 + GPT-OSS 120B | ~3 days, 10 hours |
| Gemini 3.1 Pro High + Low | ~2 days, 19 hours |
| Gemini 3 Flash | ~5 hours ← **USE THIS NOW** |

> Update this table at the start of each session with the current countdown from your quota dashboard.
