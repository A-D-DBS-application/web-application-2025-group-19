
# app/__init__.py
from flask import Flask
from flask_migrate import Migrate
from .models import db, Tenant
from .routes import main
from .config import Config

migrate = Migrate()

def create_app():
    app = Flask(__name__, template_folder="templates")
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        from . import models  # laad metadata

        # >>> SEED / RESOLVE TENANT
        # 1) Probeer eerst de geconfigureerde TENANT_ID te gebruiken
        tid_cfg = app.config.get("TENANT_ID", 1)
        t = Tenant.query.filter_by(tenant_id=tid_cfg).first()

        if not t:
            # 2) Bestaat er al een tenant? Gebruik die.
            t = Tenant.query.first()

        if not t:
            # 3) Nog geen tenant: maak er één aan ZONDER tenant_id (laat Postgres het ID genereren)
            t = Tenant(name="Default Tenant", industry="retail", contact_email="info@example.com")
            db.session.add(t)
            db.session.commit()   # hier krijgt t.tenant_id automatisch zijn waarde

        # 4) Zet de app-config naar het werkelijk bestaande tenant_id
        app.config["TENANT_ID"] = t.tenant_id

        app.register_blueprint(main)

    return app



