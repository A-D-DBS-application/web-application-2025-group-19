
# app/models.py
from datetime import datetime, date
import enum
import os
from pathlib import Path
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    ForeignKeyConstraint, UniqueConstraint, CheckConstraint, Index, Identity
)

db = SQLAlchemy()

# --- Helper for SQLite vs PostgreSQL compatibility ---
# Check if we're using SQLite by reading .env.local or env var
def _is_using_sqlite():
    """Determine if using SQLite based on env var or .env.local file."""
    # First check env var
    if os.getenv("USE_SQLITE", "").lower() == "1":
        return True
    
    # Then check .env.local file
    env_local = Path(__file__).parent.parent / ".env.local"
    if env_local.exists():
        with open(env_local) as f:
            for line in f:
                line = line.strip()
                if line.startswith("USE_SQLITE="):
                    return line.split("=", 1)[1].strip() == "1"
    
    return False

USE_SQLITE = _is_using_sqlite()

def pk_id_column(autoincrement=True, is_composite_key_part=False):
    """
    Return a primary key column that works with both SQLite and PostgreSQL.
    
    Args:
        autoincrement: Whether to enable autoincrement (only applies to single PKs or first column in composite)
        is_composite_key_part: If True, indicates this is part of a composite key. For SQLite,
                               this disables autoincrement (SQLite only supports autoincrement on single or first PK column).
    """
    if USE_SQLITE:
        # SQLite: Don't use autoincrement on non-first columns of composite keys
        if is_composite_key_part:
            return db.Column(db.Integer, primary_key=True, autoincrement=False)
        else:
            return db.Column(db.Integer, primary_key=True, autoincrement=autoincrement)
    else:
        # PostgreSQL: use Identity(always=True)
        return db.Column(db.Integer, Identity(always=True), primary_key=True)

# --- Enums ---
class EmployeeRole(enum.Enum):
    seller = "seller"
    driver = "driver"
    manager = "manager"
    admin = "admin"

class OrderStatus(enum.Enum):
    new = "new"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"

class RunStatus(enum.Enum):
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"

class DeliveryStatus(enum.Enum):
    scheduled = "scheduled"
    delivered = "delivered"
    cancelled = "cancelled"

# --- tenant ---
class Tenant(db.Model):
    __tablename__ = "tenant"
    tenant_id    = pk_id_column()
    name         = db.Column(db.String(150), unique=True, nullable=False)
    industry     = db.Column(db.String(100), default="retail")
    contact_email= db.Column(db.String(150))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    # Default regio-instellingen voor nieuwe regio's
    default_radius_km = db.Column(db.Float, default=30.0)
    default_max_deliveries = db.Column(db.Integer, default=13)

# --- region (PK: tenant_id, region_id) ---
class Region(db.Model):
    __tablename__ = "region"
    tenant_id = db.Column(db.Integer, primary_key=True)
    region_id = pk_id_column(is_composite_key_part=True)
    name      = db.Column(db.String(100), nullable=False)
    # Geografische centrum coördinaten voor regio-algoritme
    center_lat = db.Column(db.Float, nullable=True)  # Latitude van centrum
    center_lng = db.Column(db.Float, nullable=True)  # Longitude van centrum
    radius_km  = db.Column(db.Float, default=30.0)   # Straal in kilometers (standaard 30km)
    max_deliveries_per_day = db.Column(db.Integer, default=13)  # Max leveringen per dag per regio
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        UniqueConstraint("tenant_id", "name", name="uq_region_tenant_name"),
        Index("idx_region_tenant_id_name", "tenant_id", "name"),
    )

# --- region_address (adressen binnen een regio met hun coördinaten) ---
class RegionAddress(db.Model):
    __tablename__ = "region_address"
    tenant_id   = db.Column(db.Integer, primary_key=True)
    address_id  = pk_id_column(is_composite_key_part=True)
    region_id   = db.Column(db.Integer, nullable=False)
    scheduled_date = db.Column(db.Date, nullable=False)  # Datum van de levering
    address     = db.Column(db.String(300), nullable=False)
    latitude    = db.Column(db.Float, nullable=False)
    longitude   = db.Column(db.Float, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "region_id"],
                             ["region.tenant_id", "region.region_id"],
                             ondelete="CASCADE"),
        Index("idx_region_address_date", "tenant_id", "region_id", "scheduled_date"),
    )

# --- location (PK: tenant_id, location_id) ---
class Location(db.Model):
    __tablename__ = "location"
    tenant_id   = db.Column(db.Integer, primary_key=True)
    location_id = pk_id_column(is_composite_key_part=True)
    name        = db.Column(db.String(100), nullable=False)
    address     = db.Column(db.String(200))
    region_id   = db.Column(db.Integer)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "region_id"],
                             ["region.tenant_id", "region.region_id"],
                             ondelete="SET NULL"),
        UniqueConstraint("tenant_id", "name", name="uq_location_tenant_name"),
        Index("idx_location_tenant_region", "tenant_id", "region_id"),
    )

# --- employee (PK: id; unique on tenant_id+email) ---
class Employee(db.Model):
    __tablename__ = "employee"
    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Single PK for autoincrement
    tenant_id   = db.Column(db.Integer, nullable=False)
    employee_id = db.Column(db.Integer, nullable=False)  # Composite key part (no longer PK)
    location_id = db.Column(db.Integer)
    first_name  = db.Column(db.String(100), nullable=False)
    last_name   = db.Column(db.String(100), nullable=False)
    email       = db.Column(db.String(150))
    role        = db.Column(db.Enum(EmployeeRole, name="employee_role", native_enum=True),
                            nullable=False, default=EmployeeRole.seller)
    active      = db.Column(db.Boolean, default=True)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "location_id"],
                             ["location.tenant_id", "location.location_id"],
                             ondelete="SET NULL"),
        UniqueConstraint("tenant_id", "employee_id", name="uq_employee_tenant_id"),
        UniqueConstraint("tenant_id", "email", name="uq_employee_tenant_email"),
        Index("idx_employee_tenant_location", "tenant_id", "location_id"),
    )

    @property
    def username(self) -> str:
        return f"{self.first_name}.{self.last_name}".lower()

# --- availability (PK: tenant_id, availability_id) ---
class Availability(db.Model):
    __tablename__ = "availability"
    tenant_id       = db.Column(db.Integer, primary_key=True)
    availability_id = pk_id_column(is_composite_key_part=True)
    employee_id     = db.Column(db.Integer, nullable=False)
    available_date  = db.Column(db.Date, nullable=False)
    active          = db.Column(db.Boolean, default=True)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "employee_id"],
                             ["employee.tenant_id", "employee.employee_id"],
                             ondelete="CASCADE"),
        UniqueConstraint("tenant_id", "employee_id", "available_date",
                         name="uq_availability_emp_date"),
        Index("idx_availability_emp_date", "tenant_id", "employee_id", "available_date"),
    )

# --- customer (PK: tenant_id, customer_id) ---
class Customer(db.Model):
    __tablename__ = "customer"
    tenant_id   = db.Column(db.Integer, primary_key=True)
    customer_id = pk_id_column(is_composite_key_part=True)
    name        = db.Column(db.String(150), nullable=False)
    municipality= db.Column(db.String(100))
    region_id   = db.Column(db.Integer)
    phone       = db.Column(db.String(50))
    email       = db.Column(db.String(150))
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "region_id"],
                             ["region.tenant_id", "region.region_id"],
                             ondelete="SET NULL"),
        UniqueConstraint("tenant_id", "email", name="uq_customer_tenant_email"),
        Index("idx_customer_region", "tenant_id", "region_id"),
    )

# --- product (PK: tenant_id, product_id) ---
class Product(db.Model):
    __tablename__ = "product"
    tenant_id  = db.Column(db.Integer, primary_key=True)
    product_id = pk_id_column(is_composite_key_part=True)
    name       = db.Column(db.String(150), nullable=False)
    category   = db.Column(db.String(100))
    stock_qty  = db.Column(db.Integer, default=0)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        UniqueConstraint("tenant_id", "name", name="uq_product_tenant_name"),
    )

# --- customer_order (PK: tenant_id, order_id) ---
class CustomerOrder(db.Model):
    __tablename__ = "customer_order"
    tenant_id  = db.Column(db.Integer, primary_key=True)
    order_id   = pk_id_column(is_composite_key_part=True)
    customer_id= db.Column(db.Integer)
    location_id= db.Column(db.Integer)
    seller_id  = db.Column(db.Integer)
    order_date = db.Column(db.Date, default=date.today)
    status     = db.Column(db.Enum(OrderStatus, name="order_status", native_enum=True),
                           default=OrderStatus.new)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "customer_id"],
                             ["customer.tenant_id", "customer.customer_id"],
                             ondelete="SET NULL"),
        ForeignKeyConstraint(["tenant_id", "location_id"],
                             ["location.tenant_id", "location.location_id"],
                             ondelete="SET NULL"),
        ForeignKeyConstraint(["tenant_id", "seller_id"],
                             ["employee.tenant_id", "employee.employee_id"],
                             ondelete="SET NULL"),
        Index("idx_order_status", "tenant_id", "status"),
    )

# --- order_item (PK: tenant_id, order_item_id) ---
class OrderItem(db.Model):
    __tablename__ = "order_item"
    tenant_id    = db.Column(db.Integer, primary_key=True)
    order_item_id  = pk_id_column(is_composite_key_part=True)
    order_id       = db.Column(db.Integer, nullable=False)
    product_id     = db.Column(db.Integer, nullable=False)
    quantity       = db.Column(db.Integer, default=1)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "order_id"],
                             ["customer_order.tenant_id", "customer_order.order_id"],
                             ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "product_id"],
                             ["product.tenant_id", "product.product_id"],
                             ondelete="SET NULL"),
        CheckConstraint('quantity > 0', name="ck_order_item_quantity_positive"),
    )

# --- Truck Type Enum ---
class TruckType(enum.Enum):
    bestelwagen = "Bestelwagen"
    vrachtwagen = "Vrachtwagen"
    koelvoertuig = "Koelvoertuig"
    open_laadruimte = "Open laadruimte"
    speciaal_voertuig = "Speciaal voertuig"

# --- truck (fysieke voertuigen) ---
class Truck(db.Model):
    __tablename__ = "truck"
    tenant_id    = db.Column(db.Integer, primary_key=True)
    truck_id     = pk_id_column(is_composite_key_part=True)
    name         = db.Column(db.String(150), nullable=False)  # Merk & Model
    color        = db.Column(db.String(50))
    truck_type   = db.Column(db.Enum(TruckType, name="truck_type", native_enum=True),
                             default=TruckType.bestelwagen)
    capacity     = db.Column(db.String(50))  # kg of m³
    license_plate = db.Column(db.String(20))
    purchase_date = db.Column(db.Date)
    active       = db.Column(db.Boolean, default=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        UniqueConstraint("tenant_id", "license_plate", name="uq_truck_tenant_license"),
        Index("idx_truck_tenant", "tenant_id"),
    )

# --- delivery_run (PK: tenant_id, run_id) ---
class DeliveryRun(db.Model):
    __tablename__ = "delivery_run"
    tenant_id   = db.Column(db.Integer, primary_key=True)
    run_id          = pk_id_column(is_composite_key_part=True)
    scheduled_date  = db.Column(db.Date, nullable=False)
    region_id       = db.Column(db.Integer)
    driver_id       = db.Column(db.Integer)
    truck_id        = db.Column(db.Integer)  # Link naar fysieke truck
    capacity        = db.Column(db.Integer, default=10)   # max stops (optioneel)
    status          = db.Column(db.Enum(RunStatus, name="run_status", native_enum=True),
                                default=RunStatus.planned)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "region_id"],
                             ["region.tenant_id", "region.region_id"],
                             ondelete="SET NULL"),
        ForeignKeyConstraint(["tenant_id", "driver_id"],
                             ["employee.tenant_id", "employee.employee_id"],
                             ondelete="SET NULL"),
        ForeignKeyConstraint(["tenant_id", "truck_id"],
                             ["truck.tenant_id", "truck.truck_id"],
                             ondelete="SET NULL"),
        Index("idx_run_region_date", "tenant_id", "region_id", "scheduled_date"),
    )

# --- delivery (PK: tenant_id, delivery_id) ---
class Delivery(db.Model):
    __tablename__ = "delivery"
    tenant_id   = db.Column(db.Integer, primary_key=True)
    delivery_id    = pk_id_column(is_composite_key_part=True)
    order_id       = db.Column(db.Integer)
    run_id         = db.Column(db.Integer)
    delivery_status= db.Column(db.Enum(DeliveryStatus, name="delivery_status", native_enum=True),
                               default=DeliveryStatus.scheduled)
    delivered_at   = db.Column(db.DateTime)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "order_id"],
                             ["customer_order.tenant_id", "customer_order.order_id"],
                             ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "run_id"],
                             ["delivery_run.tenant_id", "delivery_run.run_id"],
                             ondelete="SET NULL"),
        Index("idx_delivery_status", "tenant_id", "delivery_status"),
    )

# --- Tijdslotregels (per categorie; aanpasbaar per tenant via DB indien gewenst) ---
TIME_SLOT_RULES = {
    "grote_matras": 15,
    "2_kleine_matras": 15,
    "boxspring": 30,
    "bodem_plus_matras": 30,
    "elektrische_boxspring": 60,
}

# ---------- Helper functies ----------

def set_employee_availability(tenant_id: int, employee_id: int, available_date: date, active: bool = True):
    av = Availability.query.filter_by(
        tenant_id=tenant_id, employee_id=employee_id, available_date=available_date
    ).first()
    if av:
        av.active = active
    else:
        availability_id = get_next_availability_id(tenant_id)
        av = Availability(
            tenant_id=tenant_id, availability_id=availability_id, employee_id=employee_id,
            available_date=available_date, active=active
        )
        db.session.add(av)
    db.session.commit()

def get_next_employee_id(tenant_id: int) -> int:
    """Get the next available employee_id for a tenant (auto-increment per tenant)."""
    max_id = db.session.query(db.func.max(Employee.employee_id)).filter(
        Employee.tenant_id == tenant_id
    ).scalar()
    return (max_id or 0) + 1

def get_next_region_id(tenant_id: int) -> int:
    """Get the next available region_id for a tenant."""
    max_id = db.session.query(db.func.max(Region.region_id)).filter(
        Region.tenant_id == tenant_id
    ).scalar()
    return (max_id or 0) + 1

def get_next_location_id(tenant_id: int) -> int:
    """Get the next available location_id for a tenant."""
    max_id = db.session.query(db.func.max(Location.location_id)).filter(
        Location.tenant_id == tenant_id
    ).scalar()
    return (max_id or 0) + 1

def get_next_customer_id(tenant_id: int) -> int:
    """Get the next available customer_id for a tenant."""
    max_id = db.session.query(db.func.max(Customer.customer_id)).filter(
        Customer.tenant_id == tenant_id
    ).scalar()
    return (max_id or 0) + 1

def get_next_product_id(tenant_id: int) -> int:
    """Get the next available product_id for a tenant."""
    max_id = db.session.query(db.func.max(Product.product_id)).filter(
        Product.tenant_id == tenant_id
    ).scalar()
    return (max_id or 0) + 1

def get_next_order_id(tenant_id: int) -> int:
    """Get the next available order_id for a tenant."""
    max_id = db.session.query(db.func.max(CustomerOrder.order_id)).filter(
        CustomerOrder.tenant_id == tenant_id
    ).scalar()
    return (max_id or 0) + 1

def get_next_order_item_id(tenant_id: int) -> int:
    """Get the next available order_item_id for a tenant."""
    max_id = db.session.query(db.func.max(OrderItem.order_item_id)).filter(
        OrderItem.tenant_id == tenant_id
    ).scalar()
    return (max_id or 0) + 1

def get_next_availability_id(tenant_id: int) -> int:
    """Get the next available availability_id for a tenant."""
    max_id = db.session.query(db.func.max(Availability.availability_id)).filter(
        Availability.tenant_id == tenant_id
    ).scalar()
    return (max_id or 0) + 1

def get_next_run_id(tenant_id: int) -> int:
    """Get the next available run_id for a tenant."""
    max_id = db.session.query(db.func.max(DeliveryRun.run_id)).filter(
        DeliveryRun.tenant_id == tenant_id
    ).scalar()
    return (max_id or 0) + 1

def get_next_delivery_id(tenant_id: int) -> int:
    """Get the next available delivery_id for a tenant."""
    max_id = db.session.query(db.func.max(Delivery.delivery_id)).filter(
        Delivery.tenant_id == tenant_id
    ).scalar()
    return (max_id or 0) + 1

def get_next_truck_id(tenant_id: int) -> int:
    """Get the next available truck_id for a tenant."""
    max_id = db.session.query(db.func.max(Truck.truck_id)).filter(
        Truck.tenant_id == tenant_id
    ).scalar()
    return (max_id or 0) + 1

def get_available_drivers(tenant_id: int, region_id: int, on_date: date):
    q = db.session.query(Employee).join(
        Location,
        (Employee.tenant_id == Location.tenant_id) & (Employee.location_id == Location.location_id)
    ).join(
        Availability,
        (Employee.tenant_id == Availability.tenant_id) & (Employee.employee_id == Availability.employee_id)
    ).filter(
        Employee.tenant_id == tenant_id,
        Employee.role == EmployeeRole.driver,
        Employee.active.is_(True),
        Location.region_id == region_id,
        Availability.available_date == on_date,
        Availability.active.is_(True),
    )
    return q.all()

def get_timeslot_duration(product_category_or_name: str) -> int:
    key = (product_category_or_name or "").strip().lower()
    return TIME_SLOT_RULES.get(key, 15)

def ensure_product(tenant_id: int, product_name: str) -> Product:
    p = Product.query.filter_by(tenant_id=tenant_id, name=product_name).first()
    if not p:
        product_id = get_next_product_id(tenant_id)
        p = Product(tenant_id=tenant_id, product_id=product_id, name=product_name, category="custom", stock_qty=9999)
        db.session.add(p)
        db.session.flush()  # krijg product_id
    return p

def compute_order_minutes(tenant_id: int, order_id: int) -> int:
    items = OrderItem.query.filter_by(tenant_id=tenant_id, order_id=order_id).all()
    total = 0
    for i in items:
        product = Product.query.filter_by(tenant_id=i.tenant_id, product_id=i.product_id).first()
        cat_or_name = (product.category or product.name or "")
        total += get_timeslot_duration(cat_or_name) * (i.quantity or 1)
    return total

def get_run_planned_minutes(tenant_id: int, run_id: int) -> int:
    deliveries = Delivery.query.filter_by(tenant_id=tenant_id, run_id=run_id).all()
    return sum(compute_order_minutes(tenant_id, d.order_id) for d in deliveries)

def add_order(tenant_id: int, customer_id: int, location_id: int, seller_id: int,
              product_name: str) -> int:
    product = ensure_product(tenant_id, product_name)
    order_id = get_next_order_id(tenant_id)
    order = CustomerOrder(
        tenant_id=tenant_id, order_id=order_id, customer_id=customer_id, location_id=location_id,
        seller_id=seller_id, order_date=date.today(), status=OrderStatus.new
    )
    db.session.add(order)
    db.session.flush()  # krijg order_id
    order_item_id = get_next_order_item_id(tenant_id)
    item = OrderItem(tenant_id=tenant_id, order_item_id=order_item_id, order_id=order.order_id,
                     product_id=product.product_id, quantity=1)
    db.session.add(item)
    db.session.commit()
    return order.order_id

def upsert_run_and_attach_delivery_with_capacity(
    tenant_id: int, order_id: int, region_id: int, driver_id: int, scheduled_date: date
) -> int:
    # 1) run zoeken of maken
    # If region_id is None, use a default region or create one
    if region_id is None:
        # Create or get a default region
        region = Region.query.filter_by(tenant_id=tenant_id, name="Default").first()
        if not region:
            region = Region(tenant_id=tenant_id, name="Default")
            db.session.add(region)
            db.session.flush()
        region_id = region.region_id
    
    run = DeliveryRun.query.filter_by(
        tenant_id=tenant_id, region_id=region_id, scheduled_date=scheduled_date
    ).with_for_update(of=DeliveryRun).first()
    if not run:
        # When attaching a delivery via scheduling, mark the run as active so it
        # does not count as an available (manually added) truck. Manually added
        # trucks created via the add-truck UI will use RunStatus.planned.
        run_id = get_next_run_id(tenant_id)
        run = DeliveryRun(
            tenant_id=tenant_id, run_id=run_id, scheduled_date=scheduled_date,
            region_id=region_id, driver_id=driver_id,
            capacity=10, status=RunStatus.in_progress
        )
        db.session.add(run)
        db.session.flush()  # krijg run_id

    # 2) Check regio-specifieke max leveringen per dag
    region = Region.query.filter_by(tenant_id=tenant_id, region_id=region_id).first()
    if region:
        max_deliveries = region.max_deliveries_per_day or 13
        delivery_count = count_deliveries_for_region_date(tenant_id, region_id, scheduled_date)
        if delivery_count >= max_deliveries:
            raise ValueError(f"Deze regio heeft al {max_deliveries} leveringen op {scheduled_date.strftime('%d-%m-%Y')}. Maximum aantal leveringen per dag bereikt.")
    
    # 3) capaciteitscontrole - simplified
    add_minutes = compute_order_minutes(tenant_id, order_id)
    used_minutes = get_run_planned_minutes(tenant_id, run.run_id)
    max_minutes = 480  # 8 uur standaard
    if used_minutes + add_minutes > max_minutes:
        raise ValueError("Capaciteit overschreden: niet genoeg minuten beschikbaar op deze route/dag.")

    # (optioneel) max stops
    if run.capacity is not None:
        current_stops = Delivery.query.filter_by(tenant_id=tenant_id, run_id=run.run_id).count()
        if current_stops + 1 > run.capacity:
            raise ValueError("Maximaal aantal stops bereikt voor deze route/dag.")

    # 4) delivery koppelen
    delivery_id = get_next_delivery_id(tenant_id)
    delivery = Delivery(
        tenant_id=tenant_id, delivery_id=delivery_id, order_id=order_id, run_id=run.run_id,
        delivery_status=DeliveryStatus.scheduled
    )
    db.session.add(delivery)
    db.session.commit()
    return delivery.delivery_id

def get_delivery_overview(tenant_id: int, region_id: int = None, order_date: date = None):
    """Get all deliveries for a tenant with their order/run info (using outer join for safety)."""
    # Return product name (from Product) instead of product_id so the listings
    # display the actual product description.
    q = db.session.query(
        Delivery.delivery_id,
        Product.name.label('product_name'),  # Get product name/description
        db.func.coalesce(Customer.municipality, Region.name).label('municipality'),  # Get municipality from Customer, fallback to Region.name
        Delivery.delivery_status,
        CustomerOrder.order_date, DeliveryRun.scheduled_date, DeliveryRun.region_id
    ).outerjoin(
        CustomerOrder,
        (Delivery.tenant_id == CustomerOrder.tenant_id) & (Delivery.order_id == CustomerOrder.order_id)
    ).outerjoin(
        Customer,
        (CustomerOrder.tenant_id == Customer.tenant_id) & (CustomerOrder.customer_id == Customer.customer_id)
    ).outerjoin(
        OrderItem,
        (CustomerOrder.tenant_id == OrderItem.tenant_id) & (CustomerOrder.order_id == OrderItem.order_id)
    ).outerjoin(
        Product,
        (OrderItem.tenant_id == Product.tenant_id) & (OrderItem.product_id == Product.product_id)
    ).outerjoin(
        DeliveryRun,
        (Delivery.tenant_id == DeliveryRun.tenant_id) & (Delivery.run_id == DeliveryRun.run_id)
    ).outerjoin(
        Region,
        (DeliveryRun.tenant_id == Region.tenant_id) & (DeliveryRun.region_id == Region.region_id)
    ).filter(Delivery.tenant_id == tenant_id)

    if region_id is not None:
        q = q.filter(DeliveryRun.region_id == region_id)
    if order_date is not None:
        q = q.filter(CustomerOrder.order_date == order_date)

    return q.order_by(DeliveryRun.scheduled_date.desc()).all()

def suggest_delivery_days(tenant_id: int, region_id: int, min_free_minutes: int = 30):
    runs = DeliveryRun.query.filter_by(tenant_id=tenant_id, region_id=region_id).all()
    suggestions = []
    max_minutes = 480  # 8 uur standaard
    for r in runs:
        free = max_minutes - get_run_planned_minutes(tenant_id, r.run_id)
        if free >= min_free_minutes and r.status == RunStatus.planned:
            suggestions.append({"date": r.scheduled_date, "free_minutes": free})
    suggestions.sort(key=lambda x: x["free_minutes"], reverse=True)
    return suggestions


# ========== GEOGRAFISCHE FUNCTIES VOOR REGIO-ALGORITME ==========

import math

def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Bereken de afstand tussen twee coördinaten in kilometers (Haversine formule).
    """
    R = 6371  # Radius van de aarde in km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = math.sin(delta_lat / 2) ** 2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def calculate_centroid(coordinates: list) -> tuple:
    """
    Bereken het geometrisch gemiddelde (centroid) van een lijst coördinaten.
    coordinates: lijst van (lat, lng) tuples
    Returns: (center_lat, center_lng)
    """
    if not coordinates:
        return None, None
    
    total_lat = sum(coord[0] for coord in coordinates)
    total_lng = sum(coord[1] for coord in coordinates)
    n = len(coordinates)
    
    return total_lat / n, total_lng / n


def get_next_address_id(tenant_id: int) -> int:
    """Get the next available address_id for a tenant."""
    max_id = db.session.query(db.func.max(RegionAddress.address_id)).filter(
        RegionAddress.tenant_id == tenant_id
    ).scalar()
    return (max_id or 0) + 1


def find_matching_regions(tenant_id: int, lat: float, lng: float, max_distance_km: float = 30.0):
    """
    Vind alle regio's waar het gegeven coördinaat binnen de straal valt.
    Returns: lijst van Region objecten met hun afstand tot het punt.
    """
    regions = Region.query.filter(
        Region.tenant_id == tenant_id,
        Region.center_lat.isnot(None),
        Region.center_lng.isnot(None)
    ).all()
    
    matching = []
    for region in regions:
        distance = haversine_distance(lat, lng, region.center_lat, region.center_lng)
        if distance <= (region.radius_km or max_distance_km):
            matching.append({
                "region": region,
                "distance_km": round(distance, 2)
            })
    
    # Sorteer op afstand (dichtsbij eerst)
    matching.sort(key=lambda x: x["distance_km"])
    return matching


def count_deliveries_for_region_date(tenant_id: int, region_id: int, scheduled_date: date) -> int:
    """
    Tel het aantal leveringen voor een specifieke regio op een specifieke datum.
    """
    count = RegionAddress.query.filter(
        RegionAddress.tenant_id == tenant_id,
        RegionAddress.region_id == region_id,
        RegionAddress.scheduled_date == scheduled_date
    ).count()
    return count


def get_available_dates_for_region(tenant_id: int, region_id: int, max_deliveries: int = None, days_ahead: int = 30):
    """
    Krijg beschikbare datums voor een regio (datums met minder dan max_deliveries).
    Als max_deliveries niet is opgegeven, wordt de waarde uit de regio gehaald.
    """
    from datetime import timedelta
    today = date.today()
    available_dates = []
    
    # Haal max_deliveries uit regio als niet opgegeven
    if max_deliveries is None:
        region = Region.query.filter_by(tenant_id=tenant_id, region_id=region_id).first()
        max_deliveries = region.max_deliveries_per_day if region else 13
    
    for i in range(days_ahead):
        check_date = today + timedelta(days=i)
        delivery_count = count_deliveries_for_region_date(tenant_id, region_id, check_date)
        
        if delivery_count < max_deliveries:
            available_dates.append({
                "date": check_date,
                "delivery_count": delivery_count,
                "spots_left": max_deliveries - delivery_count
            })
    
    return available_dates


def add_address_to_region(tenant_id: int, region_id: int, address: str, lat: float, lng: float, scheduled_date: date):
    """
    Voeg een adres toe aan een regio en herbereken het centrum.
    """
    # Voeg adres toe
    address_id = get_next_address_id(tenant_id)
    new_address = RegionAddress(
        tenant_id=tenant_id,
        address_id=address_id,
        region_id=region_id,
        scheduled_date=scheduled_date,
        address=address,
        latitude=lat,
        longitude=lng
    )
    db.session.add(new_address)
    
    # Haal alle adressen van deze regio op om het nieuwe centrum te berekenen
    all_addresses = RegionAddress.query.filter(
        RegionAddress.tenant_id == tenant_id,
        RegionAddress.region_id == region_id
    ).all()
    
    # Voeg het nieuwe adres toe aan de lijst voor berekening
    coordinates = [(addr.latitude, addr.longitude) for addr in all_addresses]
    coordinates.append((lat, lng))
    
    # Bereken nieuw centrum
    new_center_lat, new_center_lng = calculate_centroid(coordinates)
    
    # Update regio centrum
    region = Region.query.filter_by(tenant_id=tenant_id, region_id=region_id).first()
    if region:
        region.center_lat = new_center_lat
        region.center_lng = new_center_lng
    
    db.session.commit()
    return address_id


def create_new_region_with_address(tenant_id: int, region_name: str, address: str, lat: float, lng: float, scheduled_date: date):
    """
    Maak een nieuwe regio aan met het adres als centrum.
    Gebruikt de tenant defaults voor radius_km en max_deliveries_per_day.
    """
    # Haal tenant defaults op
    tenant = Tenant.query.get(tenant_id)
    default_radius = tenant.default_radius_km if tenant else 30.0
    default_max_deliveries = tenant.default_max_deliveries if tenant else 13
    
    # Maak nieuwe regio
    region_id = get_next_region_id(tenant_id)
    new_region = Region(
        tenant_id=tenant_id,
        region_id=region_id,
        name=region_name,
        center_lat=lat,
        center_lng=lng,
        radius_km=default_radius,
        max_deliveries_per_day=default_max_deliveries
    )
    db.session.add(new_region)
    db.session.flush()
    
    # Voeg adres toe aan de regio
    address_id = get_next_address_id(tenant_id)
    new_address = RegionAddress(
        tenant_id=tenant_id,
        address_id=address_id,
        region_id=region_id,
        scheduled_date=scheduled_date,
        address=address,
        latitude=lat,
        longitude=lng
    )
    db.session.add(new_address)
    db.session.commit()
    
    return region_id, address_id


# ========== CAPACITEITS FUNCTIES ==========

def count_available_drivers_for_date(tenant_id: int, check_date: date) -> int:
    """
    Tel het aantal beschikbare chauffeurs voor een specifieke datum.
    Een chauffeur is beschikbaar als:
    - role = driver
    - active = True
    - Er een Availability record bestaat voor die datum met active = True
    """
    count = db.session.query(db.func.count(Employee.employee_id)).join(
        Availability,
        (Employee.tenant_id == Availability.tenant_id) & 
        (Employee.employee_id == Availability.employee_id)
    ).filter(
        Employee.tenant_id == tenant_id,
        Employee.role == EmployeeRole.driver,
        Employee.active.is_(True),
        Availability.available_date == check_date,
        Availability.active.is_(True)
    ).scalar() or 0
    
    return count


def count_available_trucks(tenant_id: int) -> int:
    """
    Tel het totaal aantal beschikbare (actieve) trucks.
    """
    count = db.session.query(db.func.count(Truck.truck_id)).filter(
        Truck.tenant_id == tenant_id,
        Truck.active.is_(True)
    ).scalar() or 0
    
    return count


def count_active_regions_for_date(tenant_id: int, check_date: date) -> int:
    """
    Tel het aantal unieke regio's met geplande leveringen op een specifieke datum.
    Dit bepaalt hoeveel trucks er nodig zijn.
    """
    count = db.session.query(db.func.count(db.distinct(DeliveryRun.region_id))).filter(
        DeliveryRun.tenant_id == tenant_id,
        DeliveryRun.scheduled_date == check_date,
        DeliveryRun.status.in_([RunStatus.planned, RunStatus.in_progress])
    ).scalar() or 0
    
    return count


def count_total_deliveries_for_date(tenant_id: int, check_date: date) -> int:
    """
    Tel het totaal aantal leveringen gepland op een specifieke datum.
    Dit bepaalt hoeveel chauffeurs er nodig zijn.
    """
    count = db.session.query(db.func.count(Delivery.delivery_id)).join(
        DeliveryRun,
        (Delivery.tenant_id == DeliveryRun.tenant_id) & 
        (Delivery.run_id == DeliveryRun.run_id)
    ).filter(
        DeliveryRun.tenant_id == tenant_id,
        DeliveryRun.scheduled_date == check_date,
        DeliveryRun.status.in_([RunStatus.planned, RunStatus.in_progress])
    ).scalar() or 0
    
    return count


def get_capacity_info_for_date(tenant_id: int, check_date: date) -> dict:
    """
    Haal alle capaciteitsinformatie op voor een specifieke datum.
    
    VEREENVOUDIGDE REGELS:
    - Als er GEEN chauffeurs in het systeem zijn → geen beperking (algoritme werkt gewoon)
    - Als er WEL chauffeurs zijn → minstens 1 chauffeur beschikbaar per dag
    - Trucks: alleen checken als er trucks zijn, dan moeten actieve regio's ≤ trucks
    """
    available_drivers = count_available_drivers_for_date(tenant_id, check_date)
    available_trucks = count_available_trucks(tenant_id)
    active_regions = count_active_regions_for_date(tenant_id, check_date)
    total_deliveries = count_total_deliveries_for_date(tenant_id, check_date)
    
    # Tel totaal aantal chauffeurs in het systeem (ongeacht beschikbaarheid)
    total_drivers_in_system = db.session.query(db.func.count(Employee.employee_id)).filter(
        Employee.tenant_id == tenant_id,
        Employee.role == EmployeeRole.driver,
        Employee.active.is_(True)
    ).scalar() or 0
    
    is_valid = True
    reasons = []
    
    # Regel 1: Chauffeurs check (alleen als er chauffeurs in het systeem zijn)
    # Als er geen chauffeurs zijn → geen beperking
    # Als er wel chauffeurs zijn → minstens 1 beschikbaar per dag
    if total_drivers_in_system > 0 and available_drivers == 0:
        is_valid = False
        reasons.append("Geen chauffeurs beschikbaar op deze dag")
    
    # Regel 2: Trucks check (alleen als er trucks in het systeem zijn)
    # Aantal actieve regio's (+1 voor nieuwe) mag niet groter zijn dan aantal trucks
    if available_trucks > 0 and (active_regions + 1) > available_trucks:
        is_valid = False
        reasons.append(f"Trucks vol ({active_regions} regio's, {available_trucks} trucks)")
    
    # GEEN regel meer voor "leveringen ≤ chauffeurs"
    
    return {
        "available_drivers": available_drivers,
        "available_trucks": available_trucks,
        "active_regions": active_regions,
        "total_deliveries": total_deliveries,
        "total_drivers_in_system": total_drivers_in_system,
        "is_valid": is_valid,
        "reason": "; ".join(reasons) if reasons else None,
        "trucks_left": max(0, available_trucks - active_regions) if available_trucks > 0 else 999,
        "drivers_left": available_drivers if total_drivers_in_system > 0 else 999
    }


def get_suggested_dates_for_address(tenant_id: int, lat: float, lng: float, days_ahead: int = 30):
    """
    Geef datum suggesties voor een adres gebaseerd op bestaande regio's.
    
    UITGEBREID ALGORITME - Een datum is ENKEL geldig als:
    1) Er minstens één chauffeur beschikbaar is op die dag
    2) Het aantal regio's die dag NIET groter is dan het aantal beschikbare trucks
    3) Het aantal leveringen die dag NIET groter is dan het aantal beschikbare chauffeurs
    4) De regio nog < max_deliveries_per_day heeft (per regio instelling)
    """
    from datetime import timedelta
    
    # Vind regio's binnen hun eigen radius_km
    matching_regions = find_matching_regions(tenant_id, lat, lng)
    
    if not matching_regions:
        return []
    
    suggestions = []
    today = date.today()
    
    # Cache capaciteitsinfo per datum om herhaalde queries te voorkomen
    capacity_cache = {}
    
    for match in matching_regions:
        region = match["region"]
        distance = match["distance_km"]
        # Gebruik de max_deliveries_per_day van de specifieke regio
        region_max_deliveries = region.max_deliveries_per_day or 13
        
        # Check beschikbare datums voor deze regio
        for i in range(days_ahead):
            check_date = today + timedelta(days=i)
            date_str = str(check_date)
            
            # Haal capaciteitsinfo uit cache of bereken
            if date_str not in capacity_cache:
                capacity_cache[date_str] = get_capacity_info_for_date(tenant_id, check_date)
            
            capacity_info = capacity_cache[date_str]
            
            # Check capaciteitsregels
            if not capacity_info["is_valid"]:
                continue
            
            # Check regio-specifieke leveringslimiet
            delivery_count = count_deliveries_for_region_date(tenant_id, region.region_id, check_date)
            
            if delivery_count < region_max_deliveries:
                suggestions.append({
                    "date": date_str,
                    "region_id": region.region_id,
                    "region_name": region.name,
                    "distance_km": distance,
                    "delivery_count": delivery_count,
                    "spots_left": region_max_deliveries - delivery_count,
                    "max_deliveries": region_max_deliveries,  # Voeg max leveringen toe aan response
                    # Extra capaciteitsinfo
                    "available_drivers": capacity_info["available_drivers"],
                    "available_trucks": capacity_info["available_trucks"],
                    "drivers_left": capacity_info["drivers_left"],
                    "trucks_left": capacity_info["trucks_left"]
                })
    
    # Sorteer zodat datums met bestaande leveringen eerst komen
    # Prioriteit: 1) datums met leveringen (delivery_count > 0) eerst
    #             2) binnen datums met leveringen: dichtstbijzijnde eerst (distance_km)
    #             3) datums zonder leveringen daarna, gesorteerd op datum en dan afstand
    # Scheid eerst op delivery_count, dan sorteer binnen elke groep met consistente types
    suggestions_with_deliveries = [s for s in suggestions if s["delivery_count"] > 0]
    suggestions_without_deliveries = [s for s in suggestions if s["delivery_count"] == 0]
    
    # Sorteer datums met leveringen: afstand eerst, dan datum
    suggestions_with_deliveries.sort(key=lambda x: (x["distance_km"], x["date"]))
    
    # Sorteer datums zonder leveringen: datum eerst, dan afstand
    suggestions_without_deliveries.sort(key=lambda x: (x["date"], x["distance_km"]))
    
    # Combineer: eerst met leveringen, dan zonder
    suggestions = suggestions_with_deliveries + suggestions_without_deliveries
    
    # Verwijder duplicaten (alleen eerste regio per datum behouden)
    seen_dates = set()
    unique_suggestions = []
    for s in suggestions:
        if s["date"] not in seen_dates:
            seen_dates.add(s["date"])
            unique_suggestions.append(s)
    
    return unique_suggestions


