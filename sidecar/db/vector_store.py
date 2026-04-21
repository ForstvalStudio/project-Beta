import os

# AGT-01 Guardrail Requirement (GR-A01): Enforce 100% Offline Mode
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"

import lancedb
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("sidecar.vector_store")

def _find_nomic_snapshot() -> Path:
    """
    Finds nomic-embed-text-v1.5 snapshot. Priority:
    1. TAURI_RESOURCE_DIR/resources/embeddings/nomic-embed-text-v1.5 (production)
    2. ~/.cache/huggingface/hub/... (dev HF cache)
    """
    # Production: model bundled in Tauri resources
    tauri_res = os.environ.get("TAURI_RESOURCE_DIR")
    if tauri_res:
        bundled = Path(tauri_res) / "resources" / "embeddings" / "nomic-embed-text-v1.5"
        if bundled.exists():
            logger.info(f"Using bundled nomic model: {bundled}")
            return bundled

    # Dev: dynamic HF cache lookup
    snapshots_dir = (
        Path.home()
        / ".cache" / "huggingface" / "hub"
        / "models--nomic-ai--nomic-embed-text-v1.5"
        / "snapshots"
    )
    if not snapshots_dir.exists():
        logger.error(f"Snapshots directory NOT found: {snapshots_dir}")
        raise RuntimeError(
            "nomic-embed-text-v1.5 model not found in local HF cache. "
            "Please ensure models are provisioned before running sidecar."
        )

    snapshots = sorted(snapshots_dir.iterdir(), key=os.path.getmtime)
    if not snapshots:
        raise RuntimeError("nomic-embed-text-v1.5 snapshots directory is empty.")

    target_snapshot = snapshots[-1]
    logger.info(f"Dynamically resolved embedding snapshot: {target_snapshot}")
    return target_snapshot

# Global singleton to prevent repeated model initialization (performance bug)
_embedding_model = None

def get_embedding_model():
    """Returns the singleton embedding model instance, initializing it exactly once."""
    global _embedding_model
    if _embedding_model is None:
        snapshot_path = _find_nomic_snapshot()
        logger.info(f"Initialising singleton embedding model from {snapshot_path}...")
        _embedding_model = SentenceTransformer(
            str(snapshot_path),
            trust_remote_code=True,
            device="cpu",
            local_files_only=True
        )
        logger.info("Singleton embedding model loaded successfully.")
    return _embedding_model

class VectorStore:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = Path(os.environ.get("APP_DATA_DIR", "."))
            self.db_path = str(base_dir / "lancedb")
        else:
            self.db_path = db_path
        
        self.db = None
        self.table = None
        
        logger.info(f"VectorStore initialized with path: {self.db_path}")

    def connect(self):
        if self.db is None:
            self.db = lancedb.connect(self.db_path)
            logger.info("Connected to LanceDB")
        return self.db

    async def initialize_table(self, seed_data_path: str):
        db = self.connect()
        table_name = "ui_fields"
        
        if table_name in db.table_names():
            self.table = db.open_table(table_name)
            logger.info(f"Table '{table_name}' already exists")
            return

        logger.info(f"Creating and seeding table '{table_name}'...")
        with open(seed_data_path, 'r') as f:
            seed_data = json.load(f)

        # Use global singleton
        model = get_embedding_model()
        
        processed_data = []
        for item in seed_data:
            text_to_embed = f"{item['ui_field']}: {item['description']}"
            vector = model.encode(text_to_embed).tolist()
            
            processed_data.append({
                "ui_field": item["ui_field"],
                "description": item["description"],
                "data_type": item["data_type"],
                "valid_range": item["valid_range"],
                "vector": vector
            })

        self.table = db.create_table(table_name, data=processed_data)
        logger.info(f"Table '{table_name}' created and seeded with {len(processed_data)} entries")

    def search(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        if self.table is None:
            db = self.connect()
            self.table = db.open_table("ui_fields")
        
        # Use global singleton
        model = get_embedding_model()
        query_vector = model.encode(query).tolist()
        
        results = self.table.search(query_vector).limit(limit).to_list()
        return results

# Global instance for shared use
vector_store = VectorStore()
