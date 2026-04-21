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
        
        self.abs_db_path = os.path.abspath(self.db_path)
        self.conn: Optional[sqlite3.Connection] = None
        logger.info(f"DatabaseManager initialized. Absolute Path: {self.abs_db_path}")

    def connect(self):
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON;")
            
            # Diagnostic: Log columns of assets table
            try:
                cursor = self.conn.execute("PRAGMA table_info(assets)")
                columns = [row[1] for row in cursor.fetchall()]
                logger.info(f"Verified assets table columns: {columns}")
            except Exception as e:
                logger.error(f"Could not verify assets table: {e}")
                
            logger.info("Connected to SQLite database")
        return self.conn

    def log_agent_action(self, agent_id: str, action_type: str, input_data: dict, output_data: dict, status: str = "success"):
        """
        Logs an agent's action for audit and RAG improvement.
        """
        import json
        conn = self.connect()
        try:
            conn.execute(
                "INSERT INTO agent_audit_log (agent_id, action_type, input_hash, output_preview, status) VALUES (?, ?, ?, ?, ?)",
                (agent_id, action_type, json.dumps(input_data), json.dumps(output_data)[:500], status)
            )
            conn.commit()
            logger.info(f"Agent action logged: {agent_id} - {action_type}")
        except Exception as e:
            logger.error(f"Failed to log agent action: {e}")

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
        
        # Self-healing: Ensure all columns from schema.sql are present
        self.sync_schema(schema_path)

    def sync_schema(self, schema_path: str):
        """
        Parses schema.sql and adds any missing columns to existing tables.
        This provides a 'poor man's migration' system for local distribution.
        """
        logger.info("Syncing database schema (Self-Healing)...")
        conn = self.db_manager.connect()
        
        try:
            with open(schema_path, 'r') as f:
                schema_sql = f.read()

            # Simple parser to find CREATE TABLE blocks
            import re
            tables = re.findall(r'CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\);', schema_sql, re.DOTALL)
            
            for table_name, columns_block in tables:
                # Get current columns
                cursor = conn.execute(f"PRAGMA table_info({table_name})")
                existing_cols = [row[1] for row in cursor.fetchall()]
                
                # Find columns in schema block (very basic parsing)
                # Matches: "column_name TYPE"
                schema_cols = re.findall(r'^\s+(\w+)\s+', columns_block, re.MULTILINE)
                
                for col in schema_cols:
                    if col.lower() not in [ec.lower() for ec in existing_cols]:
                        logger.info(f"Adding missing column '{col}' to table '{table_name}'...")
                        # Extract the full column definition (type, defaults, etc.)
                        col_def_match = re.search(rf'^\s+{col}\s+(.*?),?$', columns_block, re.MULTILINE | re.IGNORECASE)
                        if col_def_match:
                            col_def = col_def_match.group(1).rstrip(',')
                            try:
                                conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} {col_def}")
                                conn.commit()
                                logger.info(f"Column '{col}' added successfully.")
                            except Exception as e:
                                logger.error(f"Failed to add column '{col}': {e}")
            
            logger.info("Schema sync complete")
        except Exception as e:
            logger.error(f"Error during schema sync: {e}")

# Global instance for shared use
db_manager = DatabaseManager()
migration_runner = MigrationRunner(db_manager)
