#!/usr/bin/env python
"""Script to create all missing database tables"""
import os
import sys
from pathlib import Path

# Set USE_SQLITE before importing app
os.environ["USE_SQLITE"] = "1"

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app
from app.models import db

app = create_app()

with app.app_context():
    print("Creating all database tables...")
    try:
        db.create_all()
        print("✅ All tables created successfully!")
        
        # List all tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"\n📊 Database now contains {len(tables)} tables:")
        for table in sorted(tables):
            print(f"   - {table}")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        sys.exit(1)









