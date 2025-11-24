import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "devkey123")

    # Supabase database gegevens
    SUPABASE_USER = "postgres"
    SUPABASE_PASSWORD = "sleep_inn"   # <-- jouw wachtwoord
    SUPABASE_HOST = "db.wwhwdffacdoyriqmrphs.supabase.co"  # <-- jouw Supabase host
    SUPABASE_DB = "postgres"

    # Connection string voor SQLAlchemy
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{SUPABASE_USER}:{SUPABASE_PASSWORD}"
        f"@{SUPABASE_HOST}:5432/{SUPABASE_DB}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
