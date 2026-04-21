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
from routers import asset_router, maintenance_router, forecast_router, stats_router, import_router

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sidecar")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Initializing Data Layer...")

    # 1. SQLite migrations (self-healing schema sync)
    schema_path = "../schema.sql"
    if os.path.exists(schema_path):
        migration_runner.run_initial_migration(schema_path)
    else:
        logger.error(f"schema.sql not found at {schema_path}")

    # 2. LanceDB vector store
    seed_path = "../lancedb_seed.json"
    if os.path.exists(seed_path):
        await vector_store.initialize_table(seed_path)
    else:
        logger.error(f"lancedb_seed.json not found at {seed_path}")

    # 3. Warm up AI singletons at boot — NOT on first user request
    get_embedding_model()   # nomic-embed singleton
    get_llm()               # Phi-3.5-mini singleton (no Instructor)

    logger.info("Data Layer initialization complete")

    # Log registered routes
    logger.info("Registered Routes:")
    for route in app.routes:
        methods = getattr(route, 'methods', None)
        logger.info(f"  {list(methods) if methods else 'WS'} -> {route.path}")

    yield
    # ── Shutdown (reserved) ──────────────────────────────────────────────────


app = FastAPI(title="Project Beta Sidecar", lifespan=lifespan)

# Lock down CORS to localhost only (loopback = security model per GR-S01)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "tauri://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(asset_router.router)
api_v1.include_router(maintenance_router.router)
api_v1.include_router(forecast_router.router)
api_v1.include_router(stats_router.router)
api_v1.include_router(import_router.router)

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
                if not headers:
                    await websocket.send_json({"type": "error", "message": "No headers provided"})
                    continue

                await websocket.send_json({"type": "info", "message": "Analyzing headers with AGT-01..."})

                try:
                    model_path = column_mapper.model_path
                    if os.path.exists(model_path):
                        ai_response = await column_mapper.map_columns(headers)
                    else:
                        logger.warning(f"Model not found at {model_path}. Using mock response.")
                        from agents.column_mapper import ColumnMapperResponse, MappingEntry
                        mock_mappings = [
                            MappingEntry(
                                workbook_col=h,
                                ui_field="ba_number" if "ba" in h.lower() or "reg" in h.lower() else "serial_number",
                                confidence=0.85,
                                data_type="string",
                                needs_review=False
                            )
                            for h in headers
                        ]
                        ai_response = ColumnMapperResponse(mappings=mock_mappings)

                    result = {
                        "mappings": [m.model_dump() for m in ai_response.mappings]
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
