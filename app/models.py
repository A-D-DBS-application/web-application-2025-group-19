# app/models.py
from datetime import date, time
from typing import List, Optional, Tuple
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, func

db = SQLAlchemy()

# -----------------------------
# Tables: match your schema
# -----------------------------
class Medewerker(db.Model):
    __tablename__ = "medewerker"
    id = db.Column(db.Integer, primary_key=True)
    naam = db.Column(db.String(100), nullable=False)
    rol = db.Column(db.String(20), nullable=False)          # 'verkoper', 'chauffeur', 'planner'
    beschikbaar = db.Column(db.Boolean, nullable=False, default=True)  # global availability

    # convenience
    def __repr__(self) -> str:
        return f"<Medewerker {self.naam} ({self.rol})>"


class Beschikbaarheid(db.Model):
    __tablename__ = "beschikbaarheid"
    id = db.Column(db.Integer, primary_key=True)
    medewerker_id = db.Column(db.Integer, db.ForeignKey("medewerker.id", ondelete="CASCADE"), nullable=False)
    datum = db.Column(db.Date, nullable=False)
    beschikbaar = db.Column(db.Boolean, nullable=False, default=True)

    medewerker = db.relationship("Medewerker", backref="dagen", lazy=True)

    __table_args__ = (
        db.UniqueConstraint("medewerker_id", "datum", name="uq_beschikbaarheid_per_dag"),
    )

    def __repr__(self) -> str:
        return f"<Beschikbaarheid {self.medewerker_id} {self.datum} {self.beschikbaar}>"


class Product(db.Model):
    __tablename__ = "product"
    id = db.Column(db.Integer, primary_key=True)
    naam = db.Column(db.String(100), nullable=False, index=True)
    tijdslot_minuten = db.Column(db.Integer, nullable=False, default=15)

    __table_args__ = (
        CheckConstraint("tijdslot_minuten > 0", name="ck_product_tijdslot_positive"),
    )

    def __repr__(self) -> str:
        return f"<Product {self.naam} ({self.tijdslot_minuten} min)>"


class Levering(db.Model):
    __tablename__ = "levering"
    id = db.Column(db.Integer, primary_key=True)
    datum = db.Column(db.Date, nullable=False)
    tijdstip = db.Column(db.Time, nullable=True)

    medewerker_id = db.Column(db.Integer, db.ForeignKey("medewerker.id"), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True)

    adres = db.Column(db.String(200), nullable=True)
    tijdslot_minuten = db.Column(db.Integer, nullable=False, default=15)
    handmatig = db.Column(db.Boolean, nullable=False, default=False)

    medewerker = db.relationship("Medewerker", lazy=True)
    product = db.relationship("Product", lazy=True)

    __table_args__ = (
        CheckConstraint("tijdslot_minuten > 0", name="ck_levering_tijdslot_positive"),
    )

    def __repr__(self) -> str:
        return f"<Levering {self.id} {self.datum} {self.tijdslot_minuten} min>"

# -----------------------------
# Domain helpers (business logic)
# -----------------------------

# Basic mapping from user stories (you can override with Product rows)
TIME_SLOT_RULES = {
    "grote_matras": 15,
    "2_kleine_matras": 15,
    "boxspring": 30,
    "bodem_plus_matras": 30,
    "elektrische_boxspring": 60,
}

def get_timeslot_for_product_name(product_name: str) -> int:
    if not product_name:
        return 15
    key = product_name.strip().lower()
    return TIME_SLOT_RULES.get(key, 15)

def ensure_product(naam: str) -> Product:
    """Find or create a Product, deriving tijdslot_minuten from the rules if missing."""
    key = (naam or "").strip().lower()
    product = Product.query.filter(func.lower(Product.naam) == key).first()
    if not product:
        product = Product(naam=key, tijdslot_minuten=get_timeslot_for_product_name(key))
        db.session.add(product)
        db.session.commit()
    return product

def set_medewerker_beschikbaarheid_global(medewerker_id: int, beschikbaar: bool) -> None:
    m = Medewerker.query.get(medewerker_id)
    if m:
        m.beschikbaar = bool(beschikbaar)
        db.session.commit()

def set_medewerker_beschikbaarheid_op_dag(medewerker_id: int, dag: date, beschikbaar: bool) -> None:
    rec = Beschikbaarheid.query.filter_by(medewerker_id=medewerker_id, datum=dag).first()
    if rec:
        rec.beschikbaar = bool(beschikbaar)
    else:
        rec = Beschikbaarheid(medewerker_id=medewerker_id, datum=dag, beschikbaar=bool(beschikbaar))
        db.session.add(rec)
    db.session.commit()

def is_medewerker_beschikbaar_op_dag(medewerker_id: int, dag: date) -> bool:
    """Global availability AND (per-day record true OR no record) => available."""
    m = Medewerker.query.get(medewerker_id)
    if not m or not m.beschikbaar:
        return False
    rec = Beschikbaarheid.query.filter_by(medewerker_id=medewerker_id, datum=dag).first()
    return True if (rec is None) else bool(rec.beschikbaar)

def get_beschikbare_chauffeurs(dag: date) -> List[Tuple[int, str]]:
    q = (
        db.session.query(Medewerker.id, Medewerker.naam)
        .filter(Medewerker.rol == "chauffeur", Medewerker.beschikbaar.is_(True))
        .order_by(Medewerker.naam.asc())
    ).all()
    # filter by per-day availability
    return [(m_id, naam) for (m_id, naam) in q if is_medewerker_beschikbaar_op_dag(m_id, dag)]

def werkdag_minuten() -> int:
    """Total available minutes per day for a driver. Tune via ENV or Config.WORKDAY_MINUTES."""
    from .config import Config
    return getattr(Config, "WORKDAY_MINUTES", 8 * 60)

def gebruikte_minuten_op_dag(medewerker_id: int, dag: date) -> int:
    used = (
        db.session.query(func.coalesce(func.sum(Levering.tijdslot_minuten), 0))
        .filter(Levering.medewerker_id == medewerker_id, Levering.datum == dag)
        .scalar()
    ) or 0
    return int(used)

def voldoende_capaciteit(medewerker_id: int, dag: date, extra_minuten: int) -> bool:
    return gebruikte_minuten_op_dag(medewerker_id, dag) + int(extra_minuten) <= werkdag_minuten()

def extract_municipality_from_adres(adres: Optional[str]) -> Optional[str]:
    """Very simple heuristic: take the part after the last comma."""
    if not adres:
        return None
    parts = [p.strip() for p in adres.split(",")]
    return parts[-1].lower() if parts else None

def suggest_delivery_days_by_municipality(municipality: Optional[str]) -> List[date]:
    """Suggest days where there are already deliveries in the same municipality."""
    if not municipality:
        return []
    q = (
        db.session.query(Levering.datum)
        .filter(func.lower(Levering.adres).like(f"%{municipality}%"))
        .distinct()
        .order_by(Levering.datum.asc())
    )
    return [d for (d,) in q.all()]

def create_levering(
    datum: date,
    tijdstip: Optional[time],
    medewerker_id: Optional[int],
    product_naam: Optional[str],
    adres: Optional[str],
    handmatig: bool = False,
) -> int:
    """Create a levering, validating availability and capacity if a chauffeur is chosen."""
    # product & tijdslot
    product = ensure_product(product_naam) if product_naam else None
    tijdslot = (product.tijdslot_minuten if product else 15)

    # if we assign a chauffeur, check availability + capacity
    if medewerker_id:
        if not is_medewerker_beschikbaar_op_dag(medewerker_id, datum):
            raise ValueError("Medewerker niet beschikbaar op gekozen dag.")
        if not voldoende_capaciteit(medewerker_id, datum, tijdslot):
            raise ValueError("Niet genoeg tijd beschikbaar voor deze medewerker op die dag.")

    levering = Levering(
        datum=datum,
        tijdstip=tijdstip,
        medewerker_id=medewerker_id,
        product_id=(product.id if product else None),
        adres=adres,
        tijdslot_minuten=tijdslot,
        handmatig=handmatig,
    )
    db.session.add(levering)
    db.session.commit()
    return levering.id

def get_levering_overview(datum: Optional[date] = None, medewerker_id: Optional[int] = None):
    q = (
        db.session.query(
            Levering.id.label("levering_id"),
            Levering.datum,
            Levering.tijdstip,
            Levering.tijdslot_minuten,
            Levering.adres,
            Levering.handmatig,
            Medewerker.id.label("medewerker_id"),
            Medewerker.naam.label("medewerker_naam"),
            Product.id.label("product_id"),
            Product.naam.label("product_naam"),
        )
        .outerjoin(Medewerker, Levering.medewerker_id == Medewerker.id)
        .outerjoin(Product, Levering.product_id == Product.id)
    )
    if datum:
        q = q.filter(Levering.datum == datum)
    if medewerker_id:
        q = q.filter(Levering.medewerker_id == medewerker_id)
    q = q.order_by(Levering.datum.asc(), Levering.tijdstip.asc())
    rows = [dict(r._mapping) for r in q.all()]
