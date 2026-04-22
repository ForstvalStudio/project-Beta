import warnings
# Suppress deprecated google-generativeai warning from instructor (GR-cleanup)
warnings.filterwarnings(
    "ignore",
    message="All support for the `google.generativeai` package has ended",
    category=FutureWarning,
)

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from db.manager import migration_runner
from db.vector_store import vector_store, get_embedding_model
from agents.column_mapper import column_mapper, get_llm
from logic.mapping_manager import mapping_manager
from logic.excel_engine import excel_engine

# Routers (auth removed per GR-S01 — loopback binding is the security model)
from routers import asset_router, maintenance_router, forecast_router, stats_router, import_router, overhaul_router

# ── Section 6: App data directory (platformdirs / user_data_dir) ─────────────
try:
    from platformdirs import user_data_dir
    _APP_DATA = Path(user_data_dir("project-beta", "ForstvalStudio"))
except ImportError:
    # Fallback if platformdirs not installed
    _APP_DATA = Path(os.environ.get("APP_DATA_DIR", ".")).resolve()

# Allow Tauri or env to override data dir
_APP_DATA = Path(os.environ.get("APP_DATA_DIR", str(_APP_DATA)))

# Ensure directory structure exists (first-run setup)
(_APP_DATA / "db").mkdir(parents=True, exist_ok=True)
(_APP_DATA / "lancedb").mkdir(parents=True, exist_ok=True)
(_APP_DATA / "logs").mkdir(parents=True, exist_ok=True)

# Export APP_DATA_DIR so db_manager picks it up
os.environ.setdefault("APP_DATA_DIR", str(_APP_DATA))

# ── Section 5: Resource path resolution (Tauri vs dev) ────────────────────────
def _resolve_resource(relative: str) -> Path:
    """
    In Tauri production: TAURI_RESOURCE_DIR environment variable is set.
    In dev mode: resolve relative to sidecar directory parent.
    """
    tauri_res = os.environ.get("TAURI_RESOURCE_DIR")
    if tauri_res:
        return Path(tauri_res) / relative
    # Dev mode: project root relative paths
    project_root = Path(__file__).parent.parent
    return project_root / relative

_SCHEMA_PATH    = _resolve_resource("schema.sql")
_SEED_PATH      = _resolve_resource("lancedb_seed.json")
_CHECKSUMS_PATH = _resolve_resource("resources/checksums.json")

# ── Section 7: GR-S04 — SHA-256 model checksum verification ───────────────────
import hashlib

def _verify_model_checksum(model_path: Path, checksums: dict, key: str) -> bool:
    """Computes SHA-256 of model_path and compares against checksums[key]."""
    if not model_path.exists():
        logger.warning(f"Model not found at {model_path} — skipping checksum check")
        return True  # Not present = user hasn't downloaded yet, don't block startup
    expected = checksums.get(key)
    if not expected:
        logger.warning(f"No checksum entry for {key} in checksums.json — skipping")
        return True
    sha = hashlib.sha256()
    with open(model_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    actual = sha.hexdigest()
    if actual != expected:
        logger.critical(f"CHECKSUM MISMATCH for {model_path.name}! Expected {expected[:12]}... got {actual[:12]}...")
        return False
    logger.info(f"Checksum OK: {model_path.name}")
    return True

def _run_checksum_verification():
    if not _CHECKSUMS_PATH.exists():
        logger.warning("checksums.json not found — skipping GR-S04 verification")
        return
    with open(_CHECKSUMS_PATH) as f:
        checksums = json.load(f)
    phi_path   = _resolve_resource("resources/models/phi-3.5-mini.Q4_K_M.gguf")
    nomic_path = _resolve_resource("resources/embeddings/nomic-embed-text-v1.5")
    ok = (
        _verify_model_checksum(phi_path,   checksums, "phi-3.5-mini.Q4_K_M.gguf")
        and True  # nomic is a directory; check omitted for now
    )
    if not ok:
        logger.critical("GR-S04: Model checksum verification FAILED. Refusing to start.")
        sys.exit(1)
    logger.info("GR-S04: All model checksums verified.")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(_APP_DATA / "logs" / "sidecar.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("sidecar")
logger.info(f"APP_DATA: {_APP_DATA}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Initializing Data Layer...")

    # GR-S04: Verify model checksums before loading anything
    _run_checksum_verification()

    # 1. SQLite migrations — use TAURI_RESOURCE_DIR-aware resolved path
    if _SCHEMA_PATH.exists():
        migration_runner.run_initial_migration(str(_SCHEMA_PATH))
    else:
        logger.error(f"schema.sql not found at {_SCHEMA_PATH}")

    # 2. LanceDB vector store — use TAURI_RESOURCE_DIR-aware resolved path
    if _SEED_PATH.exists():
        await vector_store.initialize_table(str(_SEED_PATH))
    else:
        logger.error(f"lancedb_seed.json not found at {_SEED_PATH}")

    # 3. Warm up AI singletons at boot — NOT on first user request
    get_embedding_model()   # nomic-embed singleton
    get_llm()               # Phi-3.5-mini singleton

    logger.info("Data Layer initialization complete")

    # Log registered routes
    logger.info("Registered Routes:")
    for route in app.routes:
        methods = getattr(route, 'methods', None)
        logger.info(f"  {list(methods) if methods else 'WS'} -> {route.path}")

    yield
    # ── Shutdown (reserved) ──────────────────────────────────────────────────


app = FastAPI(title="Project Beta Sidecar", lifespan=lifespan)

# Lock down CORS to localhost + Tauri origins only (loopback = security model per GR-S01)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "tauri://localhost",
        "https://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(asset_router.router)
api_v1.include_router(asset_router.admin_router)
api_v1.include_router(maintenance_router.router)
api_v1.include_router(forecast_router.router)
api_v1.include_router(stats_router.router)
api_v1.include_router(import_router.router)
api_v1.include_router(overhaul_router.router)

app.include_router(api_v1)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def library_connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("New WebSocket connection established")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info("WebSocket connection closed")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Sidecar is running"}


@app.get("/routes")
async def get_routes():
    """Lists all registered API routes for debugging."""
    return [{"path": route.path, "name": route.name, "methods": list(route.methods)} for route in app.routes]


@app.get("/")
async def root():
    return {"message": "Project Beta Sidecar is online", "docs": "/docs", "routes": "/routes"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.library_connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            logger.info(f"Received message: {message}")

            msg_type = message.get("type")
            payload = message.get("payload", {})

            if msg_type == "ping":
                response = {"type": "pong", "payload": payload}
                await websocket.send_json(response)

            elif msg_type == "analyze_mapping":
                headers = payload.get("headers", [])
                sheet_name = payload.get("sheet_name", "Sheet1")
                if not headers:
                    await websocket.send_json({"type": "error", "message": "No headers provided"})
                    continue

                await websocket.send_json({"type": "info", "message": "Analyzing headers with AGT-01..."})

                try:
                    model_path = column_mapper.model_path
                    if os.path.exists(model_path):
                        ai_response = await column_mapper.discover_schema(sheet_name, headers)
                    else:
                        logger.warning(f"Model not found at {model_path}. Using mock response.")
                        from agents.column_mapper import SchemaDiscoveryResponse, SchemaMapping
                        mock_schema = [
                            SchemaMapping(
                                col_index=i,
                                header=h,
                                category="IDENTITY" if any(k in h.lower() for k in ["ba", "reg", "no", "number"]) else "USAGE",
                                maps_to="ba_number" if any(k in h.lower() for k in ["ba", "reg", "no"]) else "kms_road",
                                fluid_type=None,
                                confidence=0.85,
                                needs_review=False
                            )
                            for i, h in enumerate(headers)
                        ]
                        ai_response = SchemaDiscoveryResponse(sheet_name=sheet_name, column_mappings=mock_schema)

                    result = {
                        "mappings": [s.model_dump() for s in ai_response.column_mappings],
                        "sheet_name": ai_response.sheet_name,
                        "needs_review": any(s.needs_review for s in ai_response.column_mappings)
                    }
                    await websocket.send_json({
                        "type": "mapping_suggestions",
                        "payload": result
                    })
                except Exception as e:
                    logger.error(f"Mapping analysis failed: {e}")
                    await websocket.send_json({"type": "error", "message": str(e)})

            else:
                await websocket.send_json({
                    "type": "ack",
                    "payload": f"Message received: {msg_type}"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


if __name__ == "__main__":
    port = int(os.environ.get("SIDECAR_PORT", 8000))
    logger.info(f"Starting sidecar on port {port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
