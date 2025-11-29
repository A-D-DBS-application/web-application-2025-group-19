
# app/config.py
import os

PG_DRIVER = os.getenv("PG_DRIVER", "psycopg2")  # gebruik 'psycopg2' of 'psycopg2-binary'

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "devkey123")

    # Vul hier je ECHTE Supabase gegevens in (of via .env)
    SUPABASE_USER = os.getenv("SUPABASE_USER", "postgres")
    SUPABASE_PASSWORD = os.getenv("SUPABASE_PASSWORD", "sleep_inn")  # <-- vervang in productie!
    SUPABASE_HOST = os.getenv("SUPABASE_HOST", "db.wwhwdffacdoyriqmrphs.supabase.co")
    SUPABASE_DB = os.getenv("SUPABASE_DB", "postgres")

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+{PG_DRIVER}://{SUPABASE_USER}:{SUPABASE_PASSWORD}"
        f"@{SUPABASE_HOST}:5432/{SUPABASE_DB}?sslmode=require"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TENANT_ID = int(os.getenv("TENANT_ID", "1"))

