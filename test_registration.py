from sqlalchemy import create_engine, text, inspect

# Replace with your Supabase credentials
DATABASE_URI = "postgresql+psycopg2://postgres:hzSgnWByUopBVKG8@db.wvhzyxasvblcsctzpngx.supabase.co:5432/postgres?sslmode=require"

def test_supabase_connection(uri):
    try:
        engine = create_engine(uri)
        with engine.connect() as conn:
            # Test basic connection
            result = conn.execute(text("SELECT 1"))
            print("✅ Connected to Supabase Postgres! Result:", result.fetchone())
            
            # Inspect tables
            inspector = inspect(engine)
            if "tenant" in inspector.get_table_names():
                print("✅ 'tenant' table exists")
                
                # Get columns
                columns = [col['name'] for col in inspector.get_columns("tenant")]
                print("Columns in 'tenant' table:", columns)
                
                # Check specifically for your new columns
                for col in ["default_radius_km", "default_max_deliveries"]:
                    if col in columns:
                        print(f"✅ Column '{col}' exists")
                    else:
                        print(f"❌ Column '{col}' NOT found")
            else:
                print("❌ 'tenant' table does not exist")
    except Exception as e:
        print("❌ Connection failed:", e)

if __name__ == "__main__":
    test_supabase_connection(DATABASE_URI)

