import sqlite3
import os

db_path = r"c:\Users\rohit\OneDrive\Desktop\project Beta\db\tracker.sqlite"

def test_query():
    print(f"Testing query on {db_path}...")
    if not os.path.exists(db_path):
        print("File not found")
        return
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(assets)")
        cols = [row[1] for row in cursor.fetchall()]
        print(f"Verified columns: {cols}")
        conn.close()
    except Exception as e:
        print(f"Query FAILED: {e}")

if __name__ == "__main__":
    test_query()
