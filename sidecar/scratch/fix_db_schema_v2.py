import sqlite3
import os

# Try relative and absolute paths to be safe
paths_to_check = [
    r"db/tracker.sqlite",
    r"c:\Users\rohit\OneDrive\Desktop\project Beta\sidecar\db\tracker.sqlite"
]

def run_fix():
    for db_path in paths_to_check:
        full_path = os.path.abspath(db_path)
        print(f"--- Checking database at {full_path} ---")
        if not os.path.exists(full_path):
            print(f"File does not exist: {full_path}")
            continue

        try:
            conn = sqlite3.connect(full_path)
            cursor = conn.cursor()
            
            # Check tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [t[0] for t in cursor.fetchall()]
            print(f"Tables found: {tables}")
            
            if 'assets' not in tables:
                print("Table 'assets' NOT found in this database!")
                continue
                
            cursor.execute("PRAGMA table_info(assets);")
            columns = [c[1] for c in cursor.fetchall()]
            print(f"Columns in 'assets': {columns}")
            
            if 'status' not in columns:
                print("Adding 'status' column...")
                cursor.execute("ALTER TABLE assets ADD COLUMN status TEXT DEFAULT 'Active';")
                conn.commit()
                print("Fix applied successfully.")
            else:
                print("'status' column already exists here.")
                
            conn.close()
        except Exception as e:
            print(f"Error checking {full_path}: {e}")

if __name__ == "__main__":
    run_fix()
