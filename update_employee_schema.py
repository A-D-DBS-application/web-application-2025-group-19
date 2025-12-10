#!/usr/bin/env python
"""Script to update employee table schema - adds has_co_driver and co_driver_id columns"""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "dev.db"

if not db_path.exists():
    print(f"Database not found at {db_path}")
    exit(1)

print(f"Updating employee table schema at {db_path}...")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

try:
    # Check if columns exist
    cursor.execute("PRAGMA table_info(employee)")
    columns = [row[1] for row in cursor.fetchall()]
    
    changes_made = False
    
    # Add has_co_driver if missing
    if 'has_co_driver' not in columns:
        print("Adding has_co_driver column to employee table...")
        cursor.execute("ALTER TABLE employee ADD COLUMN has_co_driver BOOLEAN DEFAULT 0")
        changes_made = True
    else:
        print("has_co_driver column already exists")
    
    # Add co_driver_id if missing
    if 'co_driver_id' not in columns:
        print("Adding co_driver_id column to employee table...")
        cursor.execute("ALTER TABLE employee ADD COLUMN co_driver_id INTEGER")
        changes_made = True
    else:
        print("co_driver_id column already exists")
    
    conn.commit()
    
    if changes_made:
        print("✅ Employee table schema updated successfully!")
    else:
        print("✅ Employee table schema is already up-to-date!")
        
except Exception as e:
    conn.rollback()
    print(f"❌ Error updating database: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
finally:
    conn.close()

