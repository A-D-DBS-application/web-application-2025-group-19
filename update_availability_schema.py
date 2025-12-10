#!/usr/bin/env python
"""Script to update availability table schema - adds morning_slot and afternoon_slot columns"""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "dev.db"

if not db_path.exists():
    print(f"Database not found at {db_path}")
    exit(1)

print(f"Updating availability table schema at {db_path}...")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

try:
    # Check if columns exist
    cursor.execute("PRAGMA table_info(availability)")
    columns = [row[1] for row in cursor.fetchall()]
    
    changes_made = False
    
    # Add morning_slot if missing
    if 'morning_slot' not in columns:
        print("Adding morning_slot column to availability table...")
        cursor.execute("ALTER TABLE availability ADD COLUMN morning_slot BOOLEAN DEFAULT 0")
        changes_made = True
    else:
        print("morning_slot column already exists")
    
    # Add afternoon_slot if missing
    if 'afternoon_slot' not in columns:
        print("Adding afternoon_slot column to availability table...")
        cursor.execute("ALTER TABLE availability ADD COLUMN afternoon_slot BOOLEAN DEFAULT 0")
        changes_made = True
    else:
        print("afternoon_slot column already exists")
    
    conn.commit()
    
    if changes_made:
        print("✅ Availability table schema updated successfully!")
    else:
        print("✅ Availability table schema is already up-to-date!")
        
except Exception as e:
    conn.rollback()
    print(f"❌ Error updating database: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
finally:
    conn.close()

