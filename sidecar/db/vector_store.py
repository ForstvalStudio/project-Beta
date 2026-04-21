import lancedb
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("sidecar.vector_store")

class VectorStore:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = Path(os.environ.get("APP_DATA_DIR", "."))
            self.db_path = str(base_dir / "lancedb")
        else:
            self.db_path = db_path
        
        self.db = None
        self.table = None
        self.model = None
        # Default local path for production offline use
        self.local_model_path = str(base_dir / "models" / "nomic-embed-text-v1.5")
        self.model_name = "nomic-ai/nomic-embed-text-v1.5"
        
        logger.info(f"VectorStore initialized with path: {self.db_path}")

    def _get_model(self):
        if self.model is None:
            # Check if local model exists for offline use
            load_path = self.local_model_path if os.path.exists(self.local_model_path) else self.model_name
            logger.info(f"Loading embedding model from: {load_path}...")
            
            self.model = SentenceTransformer(load_path, trust_remote_code=True)
            logger.info("Embedding model loaded")
        return self.model

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

        model = self._get_model()
        
        # Prepare data for LanceDB
        # We store: ui_field, description, data_type, valid_range, vector
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
        
        model = self._get_model()
        query_vector = model.encode(query).tolist()
        
        results = self.table.search(query_vector).limit(limit).to_list()
        return results

# Global instance for shared use
vector_store = VectorStore()
