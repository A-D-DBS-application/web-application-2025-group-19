import os
from app import create_app
from app.models import db

print("Creating app...")
app = create_app()

with app.app_context():
    print('DB URI:', app.config['SQLALCHEMY_DATABASE_URI'])
    print('CWD:', os.getcwd())
    
    # Check if database file exists before creating tables
    db_path = 'dev.db'
    print(f'\nBefore table creation:')
    if os.path.exists(db_path):
        print(f'✓ Database file exists at: {os.path.abspath(db_path)}')
    else:
        print(f'✗ Database file NOT found at: {os.path.abspath(db_path)}')
    
    # Force table creation (this happens in app factory, but let's try again)
    print(f'\nCreating all tables...')
    try:
        db.create_all()
        print('✓ Tables created successfully')
    except Exception as e:
        print(f'✗ Error creating tables: {e}')
    
    # Check if database file exists after creating tables
    print(f'\nAfter table creation:')
    if os.path.exists(db_path):
        size = os.path.getsize(db_path)
        print(f'✓ Database file exists at: {os.path.abspath(db_path)} (Size: {size} bytes)')
    else:
        print(f'✗ Database file STILL NOT found at: {os.path.abspath(db_path)}')
