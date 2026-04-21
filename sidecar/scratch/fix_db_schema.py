import sqlite3
import os

db_path = r"c:\Users\rohit\OneDrive\Desktop\project Beta\sidecar\db\tracker.sqlite"

def run_migration():
    print(f"Connecting to database at {db_path}...")
    if not os.path.exists(db_path):
        print("Error: Database file not found!")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Checking assets table for 'status' column...")
        cursor.execute("PRAGMA table_info(assets)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'status' not in columns:
            print("Adding 'status' column to assets table...")
            cursor.execute("ALTER TABLE assets ADD COLUMN status TEXT DEFAULT 'Active'")
            conn.commit()
            print("Successfully added 'status' column.")
        else:
            print("'status' column already exists.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
