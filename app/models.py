
# app/models.py
from datetime import datetime, date
import enum
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint

db = SQLAlchemy()

# --- Enums als strings (Postgres heeft enum types al) ---
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
    tenant_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    industry = db.Column(db.String(100), default="retail")
    contact_email = db.Column(db.String(150))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- region (PK: tenant_id, region_id) ---
class Region(db.Model):
    __tablename__ = "region"
    tenant_id = db.Column(db.Integer, primary_key=True)
    region_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        UniqueConstraint("tenant_id", "name"),
    )

# --- location (PK: tenant_id, location_id) ---
class Location(db.Model):
    __tablename__ = "location"
    tenant_id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200))
    region_id = db.Column(db.Integer)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "region_id"],
                             ["region.tenant_id", "region.region_id"],
                             ondelete="SET NULL"),
        UniqueConstraint("tenant_id", "name"),
    )

# --- employee (PK: tenant_id, employee_id) ---
class Employee(db.Model):
    __tablename__ = "employee"
    tenant_id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150))
    role = db.Column(db.Enum(EmployeeRole), nullable=False, default=EmployeeRole.seller)
    active = db.Column(db.Boolean, default=True)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "location_id"],
                             ["location.tenant_id", "location.location_id"],
                             ondelete="SET NULL"),
        UniqueConstraint("tenant_id", "email"),
    )
    @property
    def username(self) -> str:
        return f"{self.first_name}.{self.last_name}".lower()

# --- availability (PK: tenant_id, availability_id) ---
class Availability(db.Model):
    __tablename__ = "availability"
    tenant_id = db.Column(db.Integer, primary_key=True)
    availability_id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, nullable=False)
    available_date = db.Column(db.Date, nullable=False)
    active = db.Column(db.Boolean, default=True)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "employee_id"],
                             ["employee.tenant_id", "employee.employee_id"],
                             ondelete="CASCADE"),
        UniqueConstraint("tenant_id", "employee_id", "available_date"),
    )

# --- customer (PK: tenant_id, customer_id) ---
class Customer(db.Model):
    __tablename__ = "customer"
    tenant_id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    municipality = db.Column(db.String(100))
    region_id = db.Column(db.Integer)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(150))
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "region_id"],
                             ["region.tenant_id", "region.region_id"],
                             ondelete="SET NULL"),
        UniqueConstraint("tenant_id", "email"),
    )

# --- product (PK: tenant_id, product_id) ---
class Product(db.Model):
    __tablename__ = "product"
    tenant_id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(100))
    stock_qty = db.Column(db.Integer, default=0)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        UniqueConstraint("tenant_id", "name"),
    )

# --- customer_order (PK: tenant_id, order_id) ---
class CustomerOrder(db.Model):
    __tablename__ = "customer_order"
    tenant_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer)
    location_id = db.Column(db.Integer)
    seller_id = db.Column(db.Integer)
    order_date = db.Column(db.Date, default=date.today)
    status = db.Column(db.Enum(OrderStatus), default=OrderStatus.new)
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
    )

# --- order_item (PK: tenant_id, order_item_id) ---
class OrderItem(db.Model):
    __tablename__ = "order_item"
    tenant_id = db.Column(db.Integer, primary_key=True)
    order_item_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, nullable=False)
    product_id = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, default=1)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "order_id"],
                             ["customer_order.tenant_id", "customer_order.order_id"],
                             ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "product_id"],
                             ["product.tenant_id", "product.product_id"],
                             ondelete="SET NULL"),
    )

# --- delivery_run (PK: tenant_id, run_id) ---
class DeliveryRun(db.Model):
    __tablename__ = "delivery_run"
    tenant_id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, primary_key=True)
    scheduled_date = db.Column(db.Date, nullable=False)
    region_id = db.Column(db.Integer)
    driver_id = db.Column(db.Integer)
    capacity = db.Column(db.Integer, default=10)
    status = db.Column(db.Enum(RunStatus), default=RunStatus.planned)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "region_id"],
                             ["region.tenant_id", "region.region_id"],
                             ondelete="SET NULL"),
        ForeignKeyConstraint(["tenant_id", "driver_id"],
                             ["employee.tenant_id", "employee.employee_id"],
                             ondelete="SET NULL"),
    )

# --- delivery (PK: tenant_id, delivery_id) ---
class Delivery(db.Model):
    __tablename__ = "delivery"
    tenant_id = db.Column(db.Integer, primary_key=True)
    delivery_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer)
    run_id = db.Column(db.Integer)
    delivery_status = db.Column(db.Enum(DeliveryStatus), default=DeliveryStatus.scheduled)
    delivered_at = db.Column(db.DateTime)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "order_id"],
                             ["customer_order.tenant_id", "customer_order.order_id"],
                             ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "run_id"],
                             ["delivery_run.tenant_id", "delivery_run.run_id"],
                             ondelete="SET NULL"),
    )

# --- Tijdslotregels (uit user stories; geen DB-wijziging nodig) ---
TIME_SLOT_RULES = {
    "grote_matras": 15,
    "2_kleine_matras": 15,
    "boxspring": 30,
    "bodem_plus_matras": 30,
    "elektrische_boxspring": 60,
}

# ---------- Helpers die je DB NIET wijzigen ----------

def set_employee_availability(tenant_id: int, employee_id: int, available_date: date, active: bool = True):
    av = Availability.query.filter_by(
        tenant_id=tenant_id, employee_id=employee_id, available_date=available_date
    ).first()
    if av:
        av.active = active
    else:
        av = Availability(
            tenant_id=tenant_id, employee_id=employee_id,
            available_date=available_date, active=active
        )
        db.session.add(av)
    db.session.commit()

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

def get_timeslot_duration(product_name: str) -> int:
    return TIME_SLOT_RULES.get(product_name, 15)

def ensure_product(tenant_id: int, product_name: str) -> Product:
    p = Product.query.filter_by(tenant_id=tenant_id, name=product_name).first()
    if not p:
        p = Product(tenant_id=tenant_id, name=product_name, category="custom", stock_qty=9999)
        db.session.add(p)
        db.session.flush()
    return p

def add_order(tenant_id: int, customer_id: int, location_id: int, seller_id: int,
              product_name: str) -> int:
    product = ensure_product(tenant_id, product_name)
    order = CustomerOrder(
        tenant_id=tenant_id, customer_id=customer_id, location_id=location_id,
        seller_id=seller_id, order_date=date.today(), status=OrderStatus.new
    )
    db.session.add(order)
    db.session.flush()
    item = OrderItem(tenant_id=tenant_id, order_id=order.order_id,
                     product_id=product.product_id, quantity=1)
    db.session.add(item)
    db.session.commit()
    return order.order_id

def upsert_run_and_attach_delivery(tenant_id: int, order_id: int,
                                   region_id: int, driver_id: int, scheduled_date: date) -> int:
    run = DeliveryRun.query.filter_by(
        tenant_id=tenant_id, region_id=region_id, scheduled_date=scheduled_date
    ).first()
    if not run:
        run = DeliveryRun(
            tenant_id=tenant_id, scheduled_date=scheduled_date,
            region_id=region_id, driver_id=driver_id, capacity=10, status=RunStatus.planned
        )
        db.session.add(run)
        db.session.flush()
    delivery = Delivery(
        tenant_id=tenant_id, order_id=order_id, run_id=run.run_id,
        delivery_status=DeliveryStatus.scheduled
    )
    db.session.add(delivery)
    db.session.commit()
    return delivery.delivery_id

def get_delivery_overview(tenant_id: int, region_id: int = None, order_date: date = None):
    q = db.session.query(
        Delivery.delivery_id, CustomerOrder.order_id, Customer.name,
        Customer.municipality, DeliveryRun.driver_id, Delivery.delivery_status,
        CustomerOrder.order_date, DeliveryRun.scheduled_date, DeliveryRun.region_id
    ).join(
        CustomerOrder,
        (Delivery.tenant_id == CustomerOrder.tenant_id) & (Delivery.order_id == CustomerOrder.order_id)
    ).join(
        Customer,
        (CustomerOrder.tenant_id == Customer.tenant_id) & (CustomerOrder.customer_id == Customer.customer_id)
    ).join(
        Location,
        (CustomerOrder.tenant_id == Location.tenant_id) & (CustomerOrder.location_id == Location.location_id)
    ).join(
        DeliveryRun,
        (Delivery.tenant_id == DeliveryRun.tenant_id) & (Delivery.run_id == DeliveryRun.run_id)
    ).filter(Delivery.tenant_id == tenant_id)

    if region_id is not None:
        q = q.filter(DeliveryRun.region_id == region_id)
    if order_date is not None:
        q = q.filter(CustomerOrder.order_date == order_date)

    return q.order_by(DeliveryRun.scheduled_date.desc()).all()

def suggest_delivery_days(tenant_id: int, region_id: int):
    rows = db.session.query(CustomerOrder.order_date).join(
        Location,
        (CustomerOrder.tenant_id == Location.tenant_id) & (CustomerOrder.location_id == Location.location_id)
    ).filter(
        CustomerOrder.tenant_id == tenant_id,
        Location.region_id == region_id
    ).distinct().all()
    return [r[0] for r in rows]

