
# app/routes.py
from datetime import date
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from .models import (
    db, Tenant, Region, Location, Employee, Availability, Customer, Product,
    CustomerOrder, OrderItem, DeliveryRun, Delivery,
    EmployeeRole, set_employee_availability, get_available_drivers, add_order,
    upsert_run_and_attach_delivery_with_capacity, get_delivery_overview, suggest_delivery_days
)

main = Blueprint("main", __name__)

def _ensure_tenant_and_get_id() -> int:
    """
    Zorgt dat er een geldige tenant bestaat en retourneert het effectieve tenant_id.
    - Gebruikt geconfigureerde TENANT_ID indien die rij bestaat.
    - Anders pakt een bestaande tenant (eerste).
    - Anders maakt een nieuwe aan ZONDER expliciet tenant_id (Identity).
    """
    tid_cfg = int(current_app.config.get("TENANT_ID", 1))

    t = Tenant.query.filter_by(tenant_id=tid_cfg).first()
    if not t:
        t = Tenant.query.first()
    if not t:
        t = Tenant(name="Default Tenant", industry="retail", contact_email="info@example.com")
        db.session.add(t)
        db.session.commit()  # t.tenant_id wordt door Postgres gegenereerd

    # update runtime-config zodat volgende calls consistent zijn
    current_app.config["TENANT_ID"] = t.tenant_id
    return int(t.tenant_id)

def tenant_id() -> int:
    # wrapper die zeker maakt dat er een tenant bestaat
    return _ensure_tenant_and_get_id()

# --- Home (index) ---
@main.route("/", methods=["GET"])
def index():
    username = session.get("username")
    listings = []
    if "employee_id" in session:
        rows = (db.session.query(CustomerOrder.order_id, CustomerOrder.order_date)
                .filter_by(tenant_id=tenant_id(), seller_id=session["employee_id"])
                .order_by(CustomerOrder.order_date.desc())
                .all())
        listings = [{"listing_name": f"Order #{oid}", "price": 0.00} for (oid, _) in rows]
    return render_template("index.html", username=username, listings=listings)

# --- All listings (geplande deliveries) ---
@main.route("/listings", methods=["GET"])
def listings():
    rows = get_delivery_overview(tenant_id())
    items = [{"listing_name": f"{name} ({muni})", "price": 0.00} for (_d, _o, name, muni, *_rest) in rows]
    return render_template("listings.html", listings=items)

# --- Registreren ---
@main.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    first = request.form.get("firstname", "").strip()
    last  = request.form.get("lastname", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")   # UI-veld; niet opgeslagen (geen kolom in DB)

    if not first or not last or not email or not password:
        flash("Vul alle velden in.", "error")
        return redirect(url_for("main.register"))

    tid = tenant_id()  # zorgt dat tenant bestaat

    if Employee.query.filter_by(tenant_id=tid, email=email).first():
        flash("E-mailadres bestaat al.", "error")
        return redirect(url_for("main.register"))

    emp = Employee(
        tenant_id=tid, first_name=first, last_name=last,
        email=email, role=EmployeeRole.seller, active=True
    )
    db.session.add(emp)
    db.session.flush()  # <<< belangrijk: krijg employee_id rechtstreeks
    session["employee_id"] = emp.employee_id
    session["username"] = f"{emp.first_name}.{emp.last_name}".lower()
    db.session.commit()

    flash("Account aangemaakt en ingelogd.", "success")
    return redirect(url_for("main.index"))

# --- Inloggen ---
@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")   # UI-veld; niet opgeslagen

    parts = username.split(".")
    if len(parts) != 2:
        flash("Gebruik het formaat voornaam.achternaam", "error")
        return redirect(url_for("main.login"))

    first, last = parts
    tid = tenant_id()
    emp = (Employee.query
           .filter_by(tenant_id=tid, first_name=first, last_name=last, active=True)
           .first())
    if not emp:
        flash("Gebruiker niet gevonden of niet actief.", "error")
        return redirect(url_for("main.login"))

    session["employee_id"] = emp.employee_id
    session["username"] = username
    flash("Succesvol ingelogd.", "success")
    return redirect(url_for("main.index"))

# --- Uitloggen ---
@main.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Je bent uitgelogd.", "success")
    return redirect(url_for("main.index"))

# --- Add Listing -> order + order_item ---
@main.route("/add-listing", methods=["GET", "POST"])
def add_listing():
    if "employee_id" not in session:
        flash("Log in om een order toe te voegen.", "error")
        return redirect(url_for("main.login"))

    if request.method == "GET":
        return render_template("add_listing.html")

    name = request.form.get("listing_name", "").strip()
    price_raw = request.form.get("price")
    if not name or not price_raw:
        flash("Vul alle velden in.", "error")
        return redirect(url_for("main.add_listing"))

    try:
        price = float(Decimal(price_raw))
        if price < 0:
            raise ValueError()
    except Exception:
        flash("Prijs moet een positief getal zijn.", "error")
        return redirect(url_for("main.add_listing"))

    tid = tenant_id()

    # Demo customer/location — vervang later met echte UI-selecties
    customer = Customer.query.filter_by(tenant_id=tid, email="demo@customer.local").first()
    if not customer:
        customer = Customer(
            tenant_id=tid, name="Demo Customer", municipality="DemoTown",
            email="demo@customer.local"
        )
        db.session.add(customer)
        db.session.flush()

    loc = Location.query.filter_by(tenant_id=tid, name="Demo Store").first()
    if not loc:
        loc = Location(tenant_id=tid, name="Demo Store", address="Demo Street 1", region_id=None)
        db.session.add(loc); db.session.flush()

    order_id = add_order(
        tenant_id=tid,
        customer_id=customer.customer_id,
        location_id=loc.location_id,
        seller_id=session["employee_id"],
        product_name=name
    )
    flash(f"Order #{order_id} aangemaakt.", "success")
    return redirect(url_for("main.index"))

# --- Beschikbaarheid ---
@main.route("/availability", methods=["POST"])
def availability():
    if "employee_id" not in session:
        flash("Log in om beschikbaarheid te beheren.", "error")
        return redirect(url_for("main.login"))

    available_date_str = request.form.get("available_date")
    active_str = request.form.get("active", "true").lower()
    try:
        available_date = date.fromisoformat(available_date_str)
    except Exception:
        flash("Ongeldige datum (YYYY-MM-DD).", "error")
        return redirect(url_for("main.index"))

    set_employee_availability(tenant_id(), session["employee_id"], available_date, active=(active_str == "true"))
    flash(f"Beschikbaarheid ingesteld voor {available_date}.", "success")
    return redirect(url_for("main.index"))

# --- Suggesties per regio ---
@main.route("/suggest/<int:region_id>", methods=["GET"])
def suggest(region_id: int):
    suggestions = suggest_delivery_days(tenant_id(), region_id)
    if suggestions:
        msg = ", ".join([f"{s['date']} ({s['free_minutes']}m vrij)" for s in suggestions])
    else:
        msg = "geen"
    flash(f"Voorgestelde dagen voor regio {region_id}: {msg}", "info")
    return redirect(url_for("main.index"))

# --- Levering plannen ---
@main.route("/schedule", methods=["POST"])
def schedule():
    if "employee_id" not in session:
        flash("Log in om leveringen te plannen.", "error")
        return redirect(url_for("main.login"))

    tid = tenant_id()
    order_id = request.form.get("order_id")
    region_id = request.form.get("region_id")
    scheduled_date_str = request.form.get("scheduled_date")

    try:
        order_id = int(order_id)
        region_id = int(region_id) if region_id else None
        scheduled_date = date.fromisoformat(scheduled_date_str)
    except Exception:
        flash("Ongeldige invoer.", "error")
        return redirect(url_for("main.index"))

    # Kies een beschikbare driver (indien region_id gegeven)
    driver_id = None
    if region_id is not None:
        drivers = get_available_drivers(tid, region_id, scheduled_date)
        driver_id = drivers[0].employee_id if drivers else None

    try:
        delivery_id = upsert_run_and_attach_delivery_with_capacity(
            tid, order_id, region_id, driver_id, scheduled_date
        )
        flash(f"Levering #{delivery_id} gepland op {scheduled_date}.", "success")
    except ValueError as e:
        flash(str(e), "error")
    except Exception:
        db.session.rollback()
        flash("Onbekende fout bij plannen van levering.", "error")



