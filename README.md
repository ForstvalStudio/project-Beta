# Project Beta — Equipment Inventory & Maintenance Tracker

A local-first, offline-capable Tauri desktop app for fleet maintenance management, powered by a local AI sidecar (Phi-3.5-mini GGUF).

---

## 🚀 Development Startup Order

> **IMPORTANT:** You must start BOTH processes. The frontend **will not work** without the sidecar running first.

### Step 1 — Start the Python Sidecar (Terminal 1)

```bash
cd sidecar
python main.py
```

Wait until you see:
```
INFO: Application startup complete.
INFO: Uvicorn running on http://127.0.0.1:8000
```

### Step 2 — Start the Frontend (Terminal 2)

```bash
cd frontend
npm run dev
```

Then open [http://localhost:3000](http://localhost:3000).

---

## 📦 First-Time Setup

### Python Sidecar Dependencies
```bash
cd sidecar
pip install -r requirements.txt
```

### Frontend Dependencies
```bash
cd frontend
npm install
```

### AI Model Provisioning (one-time)
The AI agents require a local model. Run the setup script once:
```bash
cd sidecar
python scripts/setup_models.py
```
This will check for the required GGUF model and provide download instructions if missing.

---

## 🏗️ Architecture Overview

| Layer | Technology |
|-------|-----------|
| Desktop Shell | Tauri v2 |
| Frontend | Next.js 15 + TypeScript |
| Backend Sidecar | Python FastAPI (127.0.0.1:8000) |
| AI Mapping Agent | Phi-3.5-mini Q4_K_M (local GGUF) |
| Embeddings | nomic-embed-text-v1.5 (local HF cache) |
| Relational DB | SQLite |
| Vector DB | LanceDB |

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full system diagram.

---

## 🔒 Security Model

Per `GUARDRAILS.md` (GR-S01): **there is no authentication layer**. The loopback binding to `127.0.0.1:8000` is the security model. The sidecar is never exposed to the network.

---

## 📂 Project Structure

```
project-Beta/
├── sidecar/          # Python FastAPI AI sidecar
│   ├── agents/       # AGT-01 to AGT-05 agent logic
│   ├── routers/      # REST API route handlers
│   ├── db/           # SQLite + LanceDB managers
│   ├── models/       # AI model files (GGUF, embeddings)
│   └── main.py       # Sidecar entry point
├── frontend/         # Next.js 15 app (Tauri window)
│   └── src/
│       ├── api/      # Sidecar HTTP client with retry logic
│       ├── config/   # sidecar.ts — single URL config
│       ├── hooks/    # useSidecar — WebSocket with auto-reconnect
│       └── app/      # Page components
├── schema.sql        # SQLite schema (source of truth)
├── lancedb_seed.json # Vector store seed data for RAG
├── ARCHITECTURE.md   # Full system architecture
├── STATUS.md         # Live project state (update every session)
└── AGENTS.md         # Agent contracts and conventions
```
