"""
Migration Script: Normalize tracker.sqlite to match the ACTUAL live schema.
Creates a new clean DB from the real table structures and copies all data.
Run ONCE then delete.
"""
import sqlite3
import shutil
import os
from datetime import datetime

DB_PATH = "db/tracker.sqlite"
BACKUP_PATH = f"db/tracker_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite"

print(f"Backing up {DB_PATH} → {BACKUP_PATH}")
shutil.copy2(DB_PATH, BACKUP_PATH)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Check current asset rows
assets = conn.execute("SELECT * FROM assets").fetchall()
print(f"\nExisting assets: {len(assets)}")
for a in assets:
    print(f"  {dict(a)}")

tasks = conn.execute("SELECT COUNT(*) FROM maintenance_tasks").fetchone()[0]
overhauls = conn.execute("SELECT COUNT(*) FROM overhauls").fetchone()[0]
print(f"Maintenance tasks: {tasks}")
print(f"Overhauls: {overhauls}")

conn.close()
print("\nInspection complete. No changes made.")
