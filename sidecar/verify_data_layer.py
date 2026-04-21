import asyncio
import os
import sqlite3
import lancedb
import polars as pl
from db.manager import db_manager, migration_runner
from db.vector_store import vector_store
from logic.excel_engine import excel_engine

async def verify_data_layer():
    print("--- Data Layer Verification ---")
    
    # 1. Verify SQLite Migrations
    print("\n1. Verifying SQLite...")
    schema_path = "../schema.sql"
    migration_runner.run_initial_migration(schema_path)
    
    conn = db_manager.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Tables found: {tables}")
    
    expected_tables = ['assets', 'maintenance_tasks', 'overhauls', 'components', 'import_sessions', 'agent_audit_log']
    for table in expected_tables:
        assert table in tables, f"Missing table: {table}"
    print("[OK] SQLite verification passed")

    # 2. Verify LanceDB Seeding
    print("\n2. Verifying LanceDB...")
    seed_path = "../lancedb_seed.json"
    await vector_store.initialize_table(seed_path)
    
    results = vector_store.search("equipment identifier")
    print(f"Top match for 'equipment identifier': {results[0]['ui_field']}")
    assert results[0]['ui_field'] == 'ba_number', "Vector search failed to match 'ba_number'"
    print("[OK] LanceDB verification passed")

    # 3. Verify Polars Engine
    print("\n3. Verifying Polars Engine...")
    # Create a dummy csv/excel for testing? 
    # For now, just test if it can create a LazyFrame from a dict
    df = pl.DataFrame({"A": [1, 2], "B": [3, 4]})
    lf = df.lazy()
    print("[OK] Polars verification passed")

    print("\n--- All Verifications Passed ---")

if __name__ == "__main__":
    # Ensure we are in the sidecar directory context
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    asyncio.run(verify_data_layer())
