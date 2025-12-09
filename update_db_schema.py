#!/usr/bin/env python
"""Script to update database schema - adds missing columns to region and tenant tables"""
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
    changes_made = False
    
    # ========== REGION TABLE ==========
    cursor.execute("PRAGMA table_info(region)")
    region_columns = [row[1] for row in cursor.fetchall()]
    
    # Add center_lat if missing
    if 'center_lat' not in region_columns:
        print("Adding center_lat column to region table...")
        cursor.execute("ALTER TABLE region ADD COLUMN center_lat REAL")
        changes_made = True
    else:
        print("center_lat column already exists")
    
    # Add center_lng if missing
    if 'center_lng' not in region_columns:
        print("Adding center_lng column to region table...")
        cursor.execute("ALTER TABLE region ADD COLUMN center_lng REAL")
        changes_made = True
    else:
        print("center_lng column already exists")
    
    # Add radius_km if missing
    if 'radius_km' not in region_columns:
        print("Adding radius_km column to region table...")
        cursor.execute("ALTER TABLE region ADD COLUMN radius_km REAL DEFAULT 30.0")
        changes_made = True
    else:
        print("radius_km column already exists")
    
    # Add max_deliveries_per_day if missing
    if 'max_deliveries_per_day' not in region_columns:
        print("Adding max_deliveries_per_day column to region table...")
        cursor.execute("ALTER TABLE region ADD COLUMN max_deliveries_per_day INTEGER DEFAULT 13")
        changes_made = True
    else:
        print("max_deliveries_per_day column already exists")
    
    # ========== TENANT TABLE ==========
    cursor.execute("PRAGMA table_info(tenant)")
    tenant_columns = [row[1] for row in cursor.fetchall()]
    
    # Add default_radius_km if missing
    if 'default_radius_km' not in tenant_columns:
        print("Adding default_radius_km column to tenant table...")
        cursor.execute("ALTER TABLE tenant ADD COLUMN default_radius_km REAL DEFAULT 30.0")
        changes_made = True
    else:
        print("default_radius_km column already exists")
    
    # Add default_max_deliveries if missing
    if 'default_max_deliveries' not in tenant_columns:
        print("Adding default_max_deliveries column to tenant table...")
        cursor.execute("ALTER TABLE tenant ADD COLUMN default_max_deliveries INTEGER DEFAULT 13")
        changes_made = True
    else:
        print("default_max_deliveries column already exists")
    
    conn.commit()
    
    if changes_made:
        print("✅ Database schema updated successfully!")
    else:
        print("✅ Database schema is already up-to-date!")
        
except Exception as e:
    conn.rollback()
    print(f"❌ Error updating database: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
finally:
    conn.close()












