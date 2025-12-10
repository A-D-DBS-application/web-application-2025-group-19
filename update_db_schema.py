#!/usr/bin/env python
"""Script to update database schema - adds missing columns to region table"""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "dev.db"

if not db_path.exists():
    print(f"Database not found at {db_path}")
    exit(1)

print(f"Updating database schema at {db_path}...")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

try:
    # Check if columns exist
    cursor.execute("PRAGMA table_info(region)")
    columns = [row[1] for row in cursor.fetchall()]
    
    changes_made = False
    
    # Add center_lat if missing
    if 'center_lat' not in columns:
        print("Adding center_lat column to region table...")
        cursor.execute("ALTER TABLE region ADD COLUMN center_lat REAL")
        changes_made = True
    else:
        print("center_lat column already exists")
    
    # Add center_lng if missing
    if 'center_lng' not in columns:
        print("Adding center_lng column to region table...")
        cursor.execute("ALTER TABLE region ADD COLUMN center_lng REAL")
        changes_made = True
    else:
        print("center_lng column already exists")
    
    # Add radius_km if missing
    if 'radius_km' not in columns:
        print("Adding radius_km column to region table...")
        cursor.execute("ALTER TABLE region ADD COLUMN radius_km REAL DEFAULT 30.0")
        changes_made = True
    else:
        print("radius_km column already exists")
    
    conn.commit()
    
    if changes_made:
        print("✅ Database schema updated successfully!")
    else:
        print("✅ Database schema is already up-to-date!")
        
except Exception as e:
    conn.rollback()
    print(f"❌ Error updating database: {e}")
    exit(1)
finally:
    conn.close()












