import sqlite3
import os
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger("sidecar.db")

class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Default to a local 'data' folder in the workspace for development
            # In production, this will be overridden by the AppData path from Tauri
            base_dir = Path(os.environ.get("APP_DATA_DIR", "."))
            db_dir = base_dir / "db"
            db_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(db_dir / "tracker.sqlite")
        else:
            self.db_path = db_path
        
        self.conn: Optional[sqlite3.Connection] = None
        logger.info(f"DatabaseManager initialized with path: {self.db_path}")

    def connect(self):
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON;")
            logger.info("Connected to SQLite database")
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed")

    def execute_script(self, script_path: str):
        conn = self.connect()
        with open(script_path, 'r') as f:
            script = f.read()
        try:
            conn.executescript(script)
            conn.commit()
            logger.info(f"Executed script: {script_path}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to execute script {script_path}: {e}")
            raise

class MigrationRunner:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def run_initial_migration(self, schema_path: str):
        logger.info("Running initial migration...")
        self.db_manager.execute_script(schema_path)
        logger.info("Initial migration complete")

# Global instance for shared use
db_manager = DatabaseManager()
migration_runner = MigrationRunner(db_manager)
