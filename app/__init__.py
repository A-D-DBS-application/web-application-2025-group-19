<<<<<<< HEAD

# app/__init__.py
import os
from flask import Flask
from flask_migrate import Migrate
from .models import db
from .routes import main
=======
# app/__init__.py
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from .config import Config
from .models import db
>>>>>>> fa763f594a89d16781ff5dc80a17f22ecaa38367

migrate = Migrate()

def create_app():
    app = Flask(__name__, template_folder="templates")
<<<<<<< HEAD

    # --- Directe config (geen import van config.py nodig) ---
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "devkey123")

    # Supabase / Postgres settings
    PG_DRIVER = os.getenv("PG_DRIVER", "psycopg2")  # 'psycopg2' (psycopg2-binary) of 'psycopg'
    SUPABASE_USER = os.getenv("SUPABASE_USER", "postgres")
    SUPABASE_PASSWORD = os.getenv("SUPABASE_PASSWORD", "your_supabase_password")  # TODO: zet env-var
    SUPABASE_HOST = os.getenv("SUPABASE_HOST", "db.your-supabase.supabase.co")     # TODO: zet env-var
    SUPABASE_DB = os.getenv("SUPABASE_DB", "postgres")

    # Bij Supabase is SSL verplicht
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"postgresql+{PG_DRIVER}://{SUPABASE_USER}:{SUPABASE_PASSWORD}"
        f"@{SUPABASE_HOST}:5432/{SUPABASE_DB}?sslmode=require"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Tenant (development default)
    app.config["TENANT_ID"] = int(os.getenv("TENANT_ID", "1"))

    # --- Init extensions ---
    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        # Zorg dat Alembic metadata van modellen ziet
        from . import models  # noqa: F401
        app.register_blueprint(main)

    return app


=======
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints
    with app.app_context():
        from .routes import main
        app.register_blueprint(main)

    return app
>>>>>>> fa763f594a89d16781ff5dc80a17f22ecaa38367
