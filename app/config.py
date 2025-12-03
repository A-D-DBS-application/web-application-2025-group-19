
# app/config.py
import os
from pathlib import Path

# Load .env.local if it exists (for local development)
env_local = Path(__file__).parent.parent / ".env.local"
if env_local.exists():
    with open(env_local) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, sep, val = line.partition("=")
                if sep:
                    os.environ.setdefault(key.strip(), val.strip())

PG_DRIVER = os.getenv("PG_DRIVER", "psycopg2")  # gebruik 'psycopg2' of 'psycopg2-binary'
USE_SQLITE = os.getenv("USE_SQLITE", "0") == "1"

# Build database URI at module load time (reads env vars fresh)
if USE_SQLITE:
    # Use absolute path for SQLite on Windows
    db_path = Path(__file__).parent.parent / "dev.db"
    DATABASE_URI = f"sqlite:///{db_path}"
else:
    SUPABASE_USER = os.getenv("SUPABASE_USER", "postgres")
    SUPABASE_PASSWORD = os.getenv("SUPABASE_PASSWORD", "hzSgnWByUopBVKG8")
    SUPABASE_HOST = os.getenv("SUPABASE_HOST", "db.wvhzyxasvblcsctzpngx.supabase.co")
    SUPABASE_DB = os.getenv("SUPABASE_DB", "postgres")
    DATABASE_URI = (
        f"postgresql+{PG_DRIVER}://{SUPABASE_USER}:{SUPABASE_PASSWORD}"
        f"@{SUPABASE_HOST}:5432/{SUPABASE_DB}?sslmode=require"
    )

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "devkey123")
    SQLALCHEMY_DATABASE_URI = DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TENANT_ID = int(os.getenv("TENANT_ID", "1"))

