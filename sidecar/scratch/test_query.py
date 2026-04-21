import sqlite3
import os

db_path = r"c:\Users\rohit\OneDrive\Desktop\project Beta\sidecar\db\tracker.sqlite"

def test_query():
    print(f"Testing query on {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Check assets table structure
        cursor = conn.execute("PRAGMA table_info(assets)")
        cols = [row[1] for row in cursor.fetchall()]
        print(f"Verified columns: {cols}")
        
        # Try the failing query
        print("Running: SELECT COUNT(*) FROM assets WHERE status = 'Active'")
        count = conn.execute("SELECT COUNT(*) FROM assets WHERE status = 'Active'").fetchone()[0]
        print(f"Result: {count}")
        
        conn.close()
    except Exception as e:
        print(f"Query FAILED: {e}")

if __name__ == "__main__":
    test_query()
