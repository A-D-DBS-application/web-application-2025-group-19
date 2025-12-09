
# app/routes.py
import os
import requests
from datetime import date, timedelta, datetime
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, jsonify
from .models import (
    db, Tenant, Region, Location, Employee, Availability, Customer, Product,
    CustomerOrder, OrderItem, DeliveryRun, Delivery, RegionAddress, Truck, TruckType,
    EmployeeRole, RunStatus, set_employee_availability, get_available_drivers, add_order,
    upsert_run_and_attach_delivery_with_capacity, get_delivery_overview, suggest_delivery_days,
    find_matching_regions, get_suggested_dates_for_address, add_address_to_region,
    create_new_region_with_address, count_deliveries_for_region_date, haversine_distance,
    get_next_truck_id, get_next_employee_id, get_next_availability_id, get_capacity_info_for_date, count_available_drivers_for_date,
    count_available_trucks, count_active_regions_for_date
)
from sqlalchemy import text

# Mapbox API configuratie - wordt uit config geladen
def get_mapbox_token():
    """Haal Mapbox token uit Flask config of environment."""
    from flask import current_app
    return current_app.config.get("MAPBOX_ACCESS_TOKEN") or os.getenv(
        "MAPBOX_ACCESS_TOKEN", 
        "pk.eyJ1IjoibTFjaGFlbHYiLCJhIjoiY21pbmxsaGU4MDYzcTNkc2FyeTlkNzV1YiJ9.YVfQAyc5-VD11S3w2ACJAw"
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
    # Als gebruiker niet is ingelogd -> stuur naar login pagina
    if "employee_id" not in session:
        return redirect(url_for("main.login"))

    username = session.get("username")
    tid = tenant_id()

    # Dashboard statistics - simplified to avoid schema mismatches
    today = date.today()
    week_start = today
    week_end = today + timedelta(days=7)
    next_week_end = today + timedelta(days=14)
    
    try:
        # Normalize employee id to use for availability operations
        if existing_emp:
            employee_id_val = existing_emp.employee_id
        else:
            # either ORM-created `emp` or raw-insert created_employee_id
            if 'emp' in locals():
                employee_id_val = emp.employee_id
            else:
                employee_id_val = created_employee_id
        # 1. Geplande leveringen deze week
        deliveries_this_week = db.session.query(db.func.count(Delivery.delivery_id)).filter(
            Delivery.tenant_id == tid,
            Delivery.delivery_status == 'scheduled'
        ).scalar() or 0

        # 2. Beschikbare chauffeurs vandaag (count active drivers with availability today)
        available_drivers = db.session.query(db.func.count(Employee.employee_id)).outerjoin(
            Availability,
            (Employee.employee_id == Availability.employee_id) & (Availability.available_date == today)
        ).filter(
            Employee.tenant_id == tid,
            Employee.role == EmployeeRole.driver,
            Employee.active.is_(True),
            Availability.active.is_(True)
        ).scalar() or 0

        # 3. Beschikbare trucks (count planned delivery runs)
        available_trucks = db.session.query(db.func.count(DeliveryRun.run_id)).filter(
            DeliveryRun.tenant_id == tid,
            DeliveryRun.status == RunStatus.planned
        ).scalar() or 0

    except Exception as e:
        # Fallback if queries fail
        current_app.logger.error(f"Dashboard stats query failed: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        deliveries_this_week = 0
        available_drivers = 0
        available_trucks = 0

    # 5. Alle orders (voor listings)
    listings = []
    try:
        rows = (db.session.query(CustomerOrder.order_id, CustomerOrder.order_date)
                .filter_by(tenant_id=tid, seller_id=session["employee_id"])
                .order_by(CustomerOrder.order_date.desc())
                .all())
        listings = [{"listing_name": f"Order #{oid}", "price": 0.00} for (oid, _) in rows]
    except Exception as e:
        current_app.logger.error(f"Listings query failed: {e}")
        listings = []

    # list drivers for quick overview (all active drivers for this tenant)
    try:
        driver_rows = db.session.query(Employee).filter(
            Employee.tenant_id == tid,
            Employee.role == EmployeeRole.driver,
            Employee.active.is_(True)
        ).order_by(Employee.last_name.asc()).limit(12).all()
        drivers_list = []
        for d in driver_rows:
            # fetch the next availability date for this driver (if any)
            avail = db.session.query(Availability).filter_by(
                tenant_id=tid,
                employee_id=d.employee_id
            ).order_by(Availability.available_date.asc()).first()
            if avail and avail.available_date:
                avail_str = avail.available_date.strftime('%d-%m-%Y')
            else:
                avail_str = 'Niet ingesteld'
            drivers_list.append({
                "employee_id": d.employee_id,
                "name": f"{d.first_name} {d.last_name}",
                "available_date": avail_str
            })
    except Exception as e:
        current_app.logger.error(f"Drivers query failed: {e}")
        drivers_list = []

    # upcoming deliveries for the sidebar (all scheduled deliveries for this tenant with region/order info)
    try:
        upcoming_deliveries = db.session.query(
            Delivery.delivery_id, 
            CustomerOrder.order_id,
            Region.name,
            DeliveryRun.scheduled_date,
            RegionAddress.address,
            Delivery.delivery_status
        ).outerjoin(
            DeliveryRun,
            (Delivery.tenant_id == DeliveryRun.tenant_id) & (Delivery.run_id == DeliveryRun.run_id)
        ).outerjoin(
            Region,
            (DeliveryRun.tenant_id == Region.tenant_id) & (DeliveryRun.region_id == Region.region_id)
        ).outerjoin(
            CustomerOrder,
            (Delivery.tenant_id == CustomerOrder.tenant_id) & (Delivery.order_id == CustomerOrder.order_id)
        ).outerjoin(
            RegionAddress,
            (DeliveryRun.tenant_id == RegionAddress.tenant_id) & 
            (DeliveryRun.region_id == RegionAddress.region_id) &
            (DeliveryRun.scheduled_date == RegionAddress.scheduled_date)
        ).filter(
            Delivery.tenant_id == tid,
            Delivery.delivery_status == 'scheduled',
            DeliveryRun.scheduled_date >= date.today()  # Only future deliveries
        ).order_by(DeliveryRun.scheduled_date.asc()).limit(50).all()  # Get more to filter unique
        
        # Convert to dict format for template
        # Extract municipality from address (e.g., "Legeweg 12, 8340 Damme, West-Vlaanderen, België" -> "Damme")
        def extract_municipality(address_str):
            if not address_str:
                return 'N/A'
            # Try to extract municipality from address string
            # Format is usually: "Street, PostalCode Municipality, Province, Country"
            parts = address_str.split(',')
            if len(parts) >= 2:
                # Get the part with postal code and municipality (usually second part)
                # Format: "8340 Damme" -> extract "Damme"
                municipality_part = parts[1].strip() if len(parts) > 1 else parts[-1].strip()
                # Split by space and get the last word (municipality, skipping postal code)
                words = municipality_part.split()
                if len(words) >= 2:
                    # Skip postal code, get municipality
                    return words[-1]
                elif len(words) == 1:
                    return words[0]
            return address_str.split(',')[-1].strip() if ',' in address_str else address_str
        
        today = date.today()
        seen_combinations = set()
        unique_deliveries = []
        
        for d_id, o_id, region_name, sched_date, address, status in upcoming_deliveries:
            # Only show future deliveries
            if sched_date and sched_date < today:
                continue
                
            municipality = extract_municipality(address) if address else (region_name or 'N/A')
            
            # Create unique key: municipality + date
            unique_key = (municipality, sched_date)
            
            # Only add if we haven't seen this combination before
            if unique_key not in seen_combinations:
                seen_combinations.add(unique_key)
                unique_deliveries.append({
                    "delivery_id": d_id,
                    "order_id": o_id,
                    "municipality": municipality,
                    "scheduled_date": sched_date,
                    "delivery_status": str(status).split('.')[-1] if status else 'unknown'
                })
        
        upcoming_deliveries = unique_deliveries
    except Exception as e:
        current_app.logger.error(f"Upcoming deliveries query failed: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        upcoming_deliveries = []

    return render_template(
        "index.html",
        username=username,
        listings=listings,
        deliveries_this_week=deliveries_this_week,
        available_drivers=available_drivers,
        available_trucks=available_trucks,
        drivers_list=drivers_list,
        upcoming_deliveries=upcoming_deliveries
    )

# --- All listings (geplande deliveries) ---
@main.route("/listings", methods=["GET"])
def listings():
    if "employee_id" not in session:
        return redirect(url_for("main.login"))
    
    try:
        tid = tenant_id()
        rows = get_delivery_overview(tid)
        items = []
        for row in rows:
            try:
                # Unpack: delivery_id, product_name, region_name, status, order_date, scheduled_date, region_id
                d_id, product_name, region_name, status, order_date, sched_date, r_id = row

                # Build display info - show product_name (description) instead of product_id
                items.append({
                    "delivery_id": d_id,
                    "product_description": product_name or 'Onbekend product',  # Use product name/description
                    "municipality": region_name or 'N/A',
                    "status": str(status).split('.')[-1] if status else 'unknown',  # Extract enum value
                    "scheduled_date": sched_date
                })
            except Exception as e:
                current_app.logger.warning(f"Skipping delivery row due to unpacking error: {row}, error: {e}")
                continue
    except Exception as e:
        current_app.logger.exception(f"Error in listings route: {e}")
        items = []
    
    return render_template("listings.html", listings=items)


@main.route("/delivery/<int:delivery_id>/delete", methods=["POST"])
def delete_delivery(delivery_id):
    if "employee_id" not in session:
        flash("Log in om leveringen te verwijderen.", "error")
        return redirect(url_for("main.login"))
    
    tid = tenant_id()
    try:
        # Find and delete the delivery
        delivery = Delivery.query.filter_by(tenant_id=tid, delivery_id=delivery_id).first()
        if not delivery:
            flash("Levering niet gevonden.", "error")
            return redirect(url_for("main.listings"))
        
        db.session.delete(delivery)
        db.session.commit()
        flash(f"Levering #{delivery_id} verwijderd.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting delivery: {e}")
        flash("Kon levering niet verwijderen.", "error")
    
    return redirect(url_for("main.listings"))



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

    # Generate next employee_id for this tenant
    max_emp_id = db.session.query(db.func.max(Employee.employee_id)).filter(
        Employee.tenant_id == tid
    ).scalar() or 0
    next_emp_id = max_emp_id + 1

    # If using SQLite, use ORM insertion; if Postgres (Identity column exists),
    # use raw INSERT with OVERRIDING SYSTEM VALUE to allow explicit employee_id insertion.
    db_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
    if db_uri.startswith("sqlite:"):
        emp = Employee(
            tenant_id=tid,
            employee_id=next_emp_id,
            first_name=first,
            last_name=last,
            email=email,
            role=EmployeeRole.seller,
            active=True
        )
        db.session.add(emp)
        db.session.flush()
        session["employee_id"] = emp.employee_id
        session["username"] = f"{emp.first_name}.{emp.last_name}".lower()
        db.session.commit()
    else:
        # Postgres path: execute raw insert with OVERRIDING SYSTEM VALUE
        sql = text("""
        INSERT INTO employee (tenant_id, employee_id, location_id, first_name, last_name, email, role, active)
        VALUES (:tenant_id, :employee_id, :location_id, :first_name, :last_name, :email, :role, :active)
        OVERRIDING SYSTEM VALUE
        RETURNING id, employee_id, first_name, last_name
        """)
        params = {
            "tenant_id": tid,
            "employee_id": next_emp_id,
            "location_id": None,
            "first_name": first,
            "last_name": last,
            "email": email,
            "role": EmployeeRole.seller.value if hasattr(EmployeeRole, 'seller') else 'seller',
            "active": True,
        }
        result = db.session.execute(sql, params)
        row = result.fetchone()
        if row is None:
            db.session.rollback()
            flash("Kon account niet aanmaken (databasefout).", "error")
            return redirect(url_for("main.register"))
        # row: (id, employee_id, first_name, last_name)
        db.session.commit()
        session["employee_id"] = row[1]
        session["username"] = f"{row[2]}.{row[3]}".lower()

    flash("Account aangemaakt en ingelogd.", "success")
    return redirect(url_for("main.index"))

# --- Inloggen ---
@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")   # UI-veld; niet opgeslagen
    # Accept either fornaam.achternaam (case-insensitive) OR email address
    tid = tenant_id()
    emp = None
    parts = username.split(".")
    if len(parts) == 2:
        first, last = parts
        # case-insensitive match on first/last names
        emp = (Employee.query
               .filter(Employee.tenant_id == tid,
                       db.func.lower(Employee.first_name) == first,
                       db.func.lower(Employee.last_name) == last,
                       Employee.active.is_(True))
               .first())

    # fallback: match by e-mail (case-insensitive)
    if not emp:
        emp = (Employee.query
               .filter(Employee.tenant_id == tid,
                       db.func.lower(Employee.email) == username,
                       Employee.active.is_(True))
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


@main.route("/add-driver", methods=["POST"])
def add_driver():
    if "employee_id" not in session:
        flash("Log in om chauffeurs toe te voegen.", "error")
        return redirect(url_for("main.login"))

    first = request.form.get("first_name", "").strip()
    last = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    availability_dates_str = request.form.get("availability_dates", "").strip()

    if not first or not last or not email:
        flash("Vul voornaam, achternaam en e-mail in.", "error")
        return redirect(url_for("main.drivers_list"))

    tid = tenant_id()
    current_employee_id = session.get("employee_id")
    
    # Check if email already exists
    existing_emp = Employee.query.filter_by(tenant_id=tid, email=email).first()
    
    employee_id_val = None  # Initialize the variable
    
    if existing_emp:
        # Check if it's the same person (current logged-in user)
        if existing_emp.employee_id == current_employee_id:
            # Same person: use existing employee, update info if needed, and add availability
            emp = existing_emp
            employee_id_val = emp.employee_id  # Set the employee_id
            # Update name if provided (user might want to correct it)
            if first and first != emp.first_name:
                emp.first_name = first
            if last and last != emp.last_name:
                emp.last_name = last
            # Update role to driver so they can be used as a driver
            emp.role = EmployeeRole.driver
        else:
            # Different person with same email: prevent duplicate
            flash("E-mailadres bestaat al voor een andere medewerker.", "error")
            return redirect(url_for("main.drivers_list"))
    else:
        # Email doesn't exist: create new employee
        next_emp_id = get_next_employee_id(tid)
        db_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
        if db_uri.startswith("sqlite:"):
            emp = Employee(
                tenant_id=tid, employee_id=next_emp_id, first_name=first, last_name=last, email=email,
                role=EmployeeRole.driver, active=True
            )
            db.session.add(emp)
            db.session.flush()  # Get the id before commit
            employee_id_val = emp.employee_id  # Set the employee_id
        else:
            # Postgres: insert with OVERRIDING SYSTEM VALUE
            sql = text("""
            INSERT INTO employee (tenant_id, employee_id, location_id, first_name, last_name, email, role, active)
            VALUES (:tenant_id, :employee_id, :location_id, :first_name, :last_name, :email, :role, :active)
            OVERRIDING SYSTEM VALUE
            RETURNING id, employee_id
            """)
            params = {
                "tenant_id": tid,
                "employee_id": next_emp_id,
                "location_id": None,
                "first_name": first,
                "last_name": last,
                "email": email,
                "role": EmployeeRole.driver.value if hasattr(EmployeeRole, 'driver') else 'driver',
                "active": True,
            }
            res = db.session.execute(sql, params)
            row = res.fetchone()
            if row is None:
                db.session.rollback()
                flash("Kon chauffeur niet toevoegen (databasefout).", "error")
                return redirect(url_for("main.drivers_list"))
            db.session.flush()
            employee_id_val = row[1]  # Set the employee_id from PostgreSQL result

    # Ensure employee_id_val is set
    if employee_id_val is None:
        db.session.rollback()
        flash("Fout: Kon employee ID niet bepalen.", "error")
        return redirect(url_for("main.drivers_list"))

    try:
        # Commit employee first to ensure it exists before adding availability
        # This is important for foreign key constraints
        db.session.commit()
        current_app.logger.info(f"Committed employee {first} {last} with ID {employee_id_val}")
        
        # Parse availability dates (comma-separated)
        availability_dates = []
        if availability_dates_str:
            date_strings = [d.strip() for d in availability_dates_str.split(',') if d.strip()]
            for date_str in date_strings:
                try:
                    availability_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    availability_dates.append(availability_date)
                except ValueError:
                    current_app.logger.warning(f"Invalid date format: {date_str}")
        
        # If no dates provided, use today as default
        if not availability_dates:
            availability_dates = [date.today()]
        
        # Set availability for all selected dates
        # Get next availability_id using the helper function
        availability_errors = []
        
        for availability_date in availability_dates:
            try:
                # Check if availability already exists
                existing = Availability.query.filter_by(
                    tenant_id=tid, employee_id=employee_id_val, available_date=availability_date
                ).first()
                
                if existing:
                    # Update existing record
                    existing.active = True
                    current_app.logger.info(f"Updated existing availability for {first} {last} on {availability_date}")
                else:
                    # Create new availability record
                    availability_id = get_next_availability_id(tid)
                    
                    av = Availability(
                        tenant_id=tid, 
                        availability_id=availability_id, 
                        employee_id=employee_id_val,
                        available_date=availability_date, 
                        active=True
                    )
                    db.session.add(av)
                    current_app.logger.info(f"Added new availability for {first} {last} on {availability_date} (ID: {availability_id})")
                
            except Exception as e:
                current_app.logger.exception(f"Failed to set availability for {availability_date}: {e}")
                availability_errors.append(str(availability_date))
        
        # Commit all availability records
        if availability_errors:
            db.session.commit()  # Commit what we can
            flash(f"Chauffeur {first} {last} toegevoegd, maar beschikbaarheid kon niet worden ingesteld voor: {', '.join(availability_errors)}", "warning")
            return redirect(url_for("main.drivers_list"))
        
        db.session.commit()
        
        # Create success message with all dates
        if len(availability_dates) == 1:
            flash(f"Chauffeur {first} {last} toegevoegd en beschikbaar gemaakt voor {availability_dates[0].strftime('%d-%m-%Y')}.", "success")
        else:
            dates_str = ", ".join([d.strftime('%d-%m-%Y') for d in sorted(availability_dates)])
            flash(f"Chauffeur {first} {last} toegevoegd en beschikbaar gemaakt voor {len(availability_dates)} datums: {dates_str}.", "success")
        
        return redirect(url_for("main.drivers_list"))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error adding driver: {e}")
        error_msg = str(e)
        # Show more detailed error message to help debug
        if "NOT NULL" in error_msg or "constraint" in error_msg.lower():
            flash(f"Fout bij het toevoegen van chauffeur: Database constraint error. Details: {error_msg[:100]}", "error")
        else:
            flash(f"Fout bij het toevoegen van chauffeur: {error_msg[:150]}", "error")
    
        return redirect(url_for("main.drivers_list"))

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
    product_description = request.form.get("product_description", "").strip()
    address = request.form.get("address")
    region_name = request.form.get("region_id")  # Municipality name (optional)
    municipality = request.form.get("municipality", "").strip()  # Gemeente (optioneel, wordt uit adres gehaald indien niet opgegeven)
    scheduled_date_str = request.form.get("scheduled_date")
    
    # Extract municipality from address if not provided
    if not municipality and address:
        # Extract municipality from address (e.g., "Kerkstraat 10, 1000 Brussel, België" -> "Brussel")
        parts = address.split(',')
        if len(parts) >= 2:
            postal_part = parts[1].strip()
            postal_words = postal_part.split()
            if len(postal_words) >= 2:
                # Skip postal code, get municipality (rest of the words)
                municipality = ' '.join(postal_words[1:])
            elif len(postal_words) == 1:
                municipality = postal_words[0]
    
    # Coördinaten uit hidden fields (gezet door frontend via Mapbox)
    lat_str = request.form.get("lat", "")
    lng_str = request.form.get("lng", "")
    selected_region_id = request.form.get("selected_region_id", "")

    if not product_description:
        flash("Vul een product beschrijving in.", "error")
        return redirect(url_for("main.add_listing"))
    
    try:
        scheduled_date = date.fromisoformat(scheduled_date_str)
    except Exception:
        flash("Ongeldige datum.", "error")
        return redirect(url_for("main.add_listing"))

    # Parse coördinaten
    lat = None
    lng = None
    try:
        if lat_str and lng_str:
            lat = float(lat_str)
            lng = float(lng_str)
    except (ValueError, TypeError):
        pass

    region_id = None
    
    # ========== NIEUW REGIO-ALGORITME ==========
    if lat and lng:
        # Scenario 1: Check of er een bestaande regio is geselecteerd
        if selected_region_id:
            try:
                region_id = int(selected_region_id)
                region = Region.query.filter_by(tenant_id=tid, region_id=region_id).first()
                
                if region:
                    # Check capaciteit (max 13 leveringen)
                    delivery_count = count_deliveries_for_region_date(tid, region_id, scheduled_date)
                    if delivery_count >= 13:
                        flash(f"Deze regio heeft al 13 leveringen op {scheduled_date.strftime('%d-%m-%Y')}. Kies een andere datum.", "error")
                        return redirect(url_for("main.add_listing"))
                    
                    # Voeg adres toe aan regio en herbereken centrum
                    add_address_to_region(tid, region_id, address, lat, lng, scheduled_date)
                    current_app.logger.info(f"Added address to existing region {region_id}")
            except (ValueError, TypeError):
                pass
        
        # Scenario 2: Geen bestaande regio geselecteerd, check of adres in een regio past
        if not region_id:
            matching_regions = find_matching_regions(tid, lat, lng, max_distance_km=30.0)
            
            if matching_regions:
                # Gebruik de dichtstbijzijnde regio
                closest_region = matching_regions[0]["region"]
                region_id = closest_region.region_id
                
                # Check capaciteit
                delivery_count = count_deliveries_for_region_date(tid, region_id, scheduled_date)
                if delivery_count >= 13:
                    # Probeer de volgende dichtstbijzijnde regio
                    found_available = False
                    for match in matching_regions[1:]:
                        r = match["region"]
                        count = count_deliveries_for_region_date(tid, r.region_id, scheduled_date)
                        if count < 13:
                            region_id = r.region_id
                            found_available = True
                            break
                    
                    if not found_available:
                        # Alle regio's vol, maak nieuwe regio
                        region_name_new = municipality or region_name or f"Regio {scheduled_date.strftime('%d-%m-%Y')}"
                        region_id, _ = create_new_region_with_address(tid, region_name_new, address, lat, lng, scheduled_date)
                        current_app.logger.info(f"Created new region {region_id} (all nearby regions full)")
                else:
                    # Voeg adres toe aan bestaande regio
                    add_address_to_region(tid, region_id, address, lat, lng, scheduled_date)
                    current_app.logger.info(f"Added address to nearest region {region_id}")
            else:
                # Geen bestaande regio binnen 30km, maak nieuwe regio
                region_name_new = municipality or region_name or f"Regio {scheduled_date.strftime('%d-%m-%Y')}"
                region_id, _ = create_new_region_with_address(tid, region_name_new, address, lat, lng, scheduled_date)
                current_app.logger.info(f"Created new region {region_id} (no nearby regions)")
    
    # Fallback: oude logica als geen coördinaten beschikbaar
    if not region_id and region_name:
        region = Region.query.filter_by(tenant_id=tid, name=region_name).first()
        if region:
            region_id = region.region_id
        else:
            from .models import get_next_region_id
            region_id = get_next_region_id(tid)
            region = Region(tenant_id=tid, region_id=region_id, name=region_name)
            db.session.add(region)
            db.session.flush()

    # Kies een beschikbare driver (indien region_id gegeven)
    driver_id = None
    if region_id is not None:
        drivers = get_available_drivers(tid, region_id, scheduled_date)
        driver_id = drivers[0].employee_id if drivers else None

    # Always create a new order with the product description
    try:
        # Ensure we have a valid region_id before creating location
        if region_id is None:
            # Create a default region if none exists
            from .models import get_next_region_id
            default_region = Region.query.filter_by(tenant_id=tid, name="Default").first()
            if not default_region:
                region_id_new = get_next_region_id(tid)
                default_region = Region(tenant_id=tid, region_id=region_id_new, name="Default", radius_km=30.0)
                db.session.add(default_region)
                db.session.flush()
            region_id = default_region.region_id
        
        # create demo customer/location if needed
        customer = Customer.query.filter_by(tenant_id=tid, email="demo@customer.local").first()
        if not customer:
            from .models import get_next_customer_id
            customer_id = get_next_customer_id(tid)
            customer = Customer(tenant_id=tid, customer_id=customer_id, name="Demo Customer", municipality="DemoTown", email="demo@customer.local")
            db.session.add(customer)
            db.session.flush()

        # Use address from form if provided for the initial demo location, otherwise use default.
        location_address = address if address else "Demo Street 1"
        loc = Location.query.filter_by(tenant_id=tid, name="Demo Store").first()
        if not loc:
            from .models import get_next_location_id
            location_id = get_next_location_id(tid)
            loc = Location(
                tenant_id=tid,
                location_id=location_id,
                name="Demo Store",
                address=location_address,
                region_id=region_id,
            )
            db.session.add(loc)
            db.session.flush()

        # create a new order with the product description
        new_order_id = add_order(tenant_id=tid, customer_id=customer.customer_id, location_id=loc.location_id, seller_id=session["employee_id"], product_name=product_description)
        order_id = int(new_order_id)
        current_app.logger.info(f"Created order {order_id} for scheduling with product: {product_description}")
    except Exception as e:
        current_app.logger.exception(f"Failed to create order for schedule request: {e}")
        flash(f"Kon geen order aanmaken voor deze levering: {str(e)}", "error")
        return redirect(url_for("main.add_listing"))

    try:
        delivery_id = upsert_run_and_attach_delivery_with_capacity(
            tid, order_id, region_id, driver_id, scheduled_date
        )
        # Format date for user-facing message (dd-mm-YYYY)
        try:
            sched_str = scheduled_date.strftime('%d-%m-%Y')
        except Exception:
            sched_str = str(scheduled_date)
        flash(f"Levering #{delivery_id} gepland op {sched_str}.", "success")
    except ValueError as e:
        # Known business rule error (capacity etc.)
        current_app.logger.warning(f"Scheduling validation error: {e}")
        flash(str(e), "error")
    except Exception as e:
        # Unexpected error: rollback, log full traceback and show helpful message
        db.session.rollback()
        import traceback
        tb = traceback.format_exc()
        error_msg = f"Schedule unexpected error: {str(e)}\n{tb}"
        current_app.logger.error(error_msg)
        # Provide more context to the user while keeping it readable
        short_msg = str(e) if str(e) else "Interne serverfout"
        flash(f"Onbekende fout bij plannen van levering: {short_msg}", "error")
    
    return redirect(url_for("main.add_listing"))


# --- API endpoints voor beschikbaarheid en suggesties ---
@main.route("/api/availability/<date_str>", methods=["GET"])
def get_availability(date_str):
    """Get driver and truck availability for a specific date."""
    if "employee_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        selected_date = date.fromisoformat(date_str)
    except Exception:
        return jsonify({"error": "Invalid date format"}), 400
    
    tid = tenant_id()
    
    # Get available drivers for this date
    drivers = db.session.query(
        Employee.employee_id,
        Employee.first_name,
        Employee.last_name,
        Location.address,
        Region.name.label('region_name')
    ).join(
        Availability,
        (Employee.tenant_id == Availability.tenant_id) & 
        (Employee.employee_id == Availability.employee_id)
    ).outerjoin(
        Location,
        (Employee.tenant_id == Location.tenant_id) & 
        (Employee.location_id == Location.location_id)
    ).outerjoin(
        Region,
        (Location.tenant_id == Region.tenant_id) & 
        (Location.region_id == Region.region_id)
    ).filter(
        Employee.tenant_id == tid,
        Employee.role == EmployeeRole.driver,
        Employee.active.is_(True),
        Availability.available_date == selected_date,
        Availability.active.is_(True)
    ).all()
    
    driver_list = [
        {
            "id": d.employee_id,
            "name": f"{d.first_name} {d.last_name}",
            "region": d.region_name or "Niet ingesteld"
        }
        for d in drivers
    ]
    
    # Get available trucks (planned runs) for this date
    trucks = db.session.query(
        DeliveryRun.run_id,
        DeliveryRun.capacity,
        Region.name.label('region_name'),
        Employee.first_name,
        Employee.last_name
    ).outerjoin(
        Region,
        (DeliveryRun.tenant_id == Region.tenant_id) & 
        (DeliveryRun.region_id == Region.region_id)
    ).outerjoin(
        Employee,
        (DeliveryRun.tenant_id == Employee.tenant_id) & 
        (DeliveryRun.driver_id == Employee.employee_id)
    ).filter(
        DeliveryRun.tenant_id == tid,
        DeliveryRun.scheduled_date == selected_date,
        DeliveryRun.status == RunStatus.planned
    ).all()
    
    # Count deliveries per truck
    truck_list = []
    for truck in trucks:
        delivery_count = db.session.query(db.func.count(Delivery.delivery_id)).filter(
            Delivery.tenant_id == tid,
            Delivery.run_id == truck.run_id
        ).scalar() or 0
        
        driver_name = None
        if truck.first_name and truck.last_name:
            driver_name = f"{truck.first_name} {truck.last_name}"
        
        truck_list.append({
            "id": truck.run_id,
            "region": truck.region_name or "Niet ingesteld",
            "capacity": truck.capacity or 10,
            "used": delivery_count,
            "driver": driver_name or "Niet toegewezen"
        })
    
    return jsonify({
        "date": date_str,
        "drivers": driver_list,
        "trucks": truck_list
    })


@main.route("/api/suggest-dates", methods=["GET"])
def suggest_dates():
    """Suggest dates with deliveries in the same region."""
    if "employee_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    region_name = request.args.get("region")
    if not region_name:
        return jsonify({"suggestions": []})
    
    tid = tenant_id()
    
    # Find region by name
    region = Region.query.filter_by(tenant_id=tid, name=region_name).first()
    if not region:
        return jsonify({"suggestions": []})
    
    # Get dates with deliveries in this region (next 30 days)
    today = date.today()
    future_date = today + timedelta(days=30)
    
    runs = db.session.query(
        DeliveryRun.scheduled_date,
        db.func.count(Delivery.delivery_id).label('delivery_count')
    ).outerjoin(
        Delivery,
        (DeliveryRun.tenant_id == Delivery.tenant_id) & 
        (DeliveryRun.run_id == Delivery.run_id)
    ).filter(
        DeliveryRun.tenant_id == tid,
        DeliveryRun.region_id == region.region_id,
        DeliveryRun.scheduled_date >= today,
        DeliveryRun.scheduled_date <= future_date
    ).group_by(DeliveryRun.scheduled_date).order_by(DeliveryRun.scheduled_date.asc()).all()
    
    suggestions = [
        {
            "date": str(run.scheduled_date),
            "delivery_count": run.delivery_count
        }
        for run in runs
    ]
    
    return jsonify({"suggestions": suggestions})


# ========== NIEUWE API ENDPOINTS VOOR REGIO-ALGORITME ==========

@main.route("/api/geocode", methods=["GET"])
def geocode_address():
    """
    Geocode een adres via Mapbox API.
    Returns: { lat, lng, formatted_address }
    """
    if "employee_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    address = request.args.get("address", "").strip()
    if not address:
        return jsonify({"error": "Address is required"}), 400
    
    try:
        # Mapbox Geocoding API aanroepen
        mapbox_token = get_mapbox_token()
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{requests.utils.quote(address)}.json"
        params = {
            "access_token": mapbox_token,
            "limit": 1,
            "country": "BE,NL,LU,DE,FR",  # Focus op Benelux en omgeving
            "language": "nl"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("features"):
            return jsonify({"error": "Address not found"}), 404
        
        feature = data["features"][0]
        lng, lat = feature["center"]  # Mapbox returns [lng, lat]
        
        return jsonify({
            "lat": lat,
            "lng": lng,
            "formatted_address": feature.get("place_name", address)
        })
        
    except requests.RequestException as e:
        current_app.logger.error(f"Mapbox geocoding error: {e}")
        return jsonify({"error": "Geocoding service unavailable"}), 503
    except Exception as e:
        current_app.logger.error(f"Geocoding error: {e}")
        return jsonify({"error": "Internal error"}), 500


@main.route("/api/suggest-dates-by-location", methods=["GET"])
def suggest_dates_by_location():
    """
    Geef datum suggesties gebaseerd op coördinaten van een adres.
    - Vindt regio's binnen 30km
    - Toont alleen datums met < 13 leveringen
    """
    if "employee_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        lat = float(request.args.get("lat", 0))
        lng = float(request.args.get("lng", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid coordinates"}), 400
    
    if lat == 0 or lng == 0:
        return jsonify({"error": "Coordinates required"}), 400
    
    tid = tenant_id()
    max_deliveries = 13  # Maximum leveringen per dag per regio
    
    try:
        # Gebruik het nieuwe algoritme om suggesties te krijgen
        suggestions = get_suggested_dates_for_address(tid, lat, lng, max_deliveries, days_ahead=30)
        
        return jsonify({
            "suggestions": suggestions,
            "has_matching_regions": len(suggestions) > 0
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting date suggestions: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": "Internal error"}), 500


@main.route("/api/check-region-capacity", methods=["GET"])
def check_region_capacity():
    """
    Check de capaciteit van een regio voor een specifieke datum.
    """
    if "employee_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        region_id = int(request.args.get("region_id", 0))
        date_str = request.args.get("date", "")
        check_date = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid parameters"}), 400
    
    tid = tenant_id()
    max_deliveries = 13
    
    delivery_count = count_deliveries_for_region_date(tid, region_id, check_date)
    
    return jsonify({
        "region_id": region_id,
        "date": date_str,
        "delivery_count": delivery_count,
        "max_deliveries": max_deliveries,
        "spots_left": max_deliveries - delivery_count,
        "is_available": delivery_count < max_deliveries
    })


@main.route("/api/check-daily-capacity", methods=["GET"])
def check_daily_capacity():
    """
    Check de totale capaciteit (chauffeurs + trucks) voor een specifieke datum.
    Retourneert:
    - available_drivers: beschikbare chauffeurs
    - available_trucks: totaal trucks
    - active_regions: regio's met leveringen
    - total_deliveries: totaal leveringen
    - is_valid: of er nog capaciteit is
    - reason: reden indien niet beschikbaar
    """
    if "employee_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        date_str = request.args.get("date", "")
        check_date = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid date parameter"}), 400
    
    tid = tenant_id()
    capacity_info = get_capacity_info_for_date(tid, check_date)
    
    return jsonify({
        "date": date_str,
        **capacity_info
    })


# --- Truck Management ---
@main.route("/trucks", methods=["GET"])
def trucks_list():
    """Show all trucks (physical vehicles) for current tenant."""
    if "employee_id" not in session:
        return redirect(url_for("main.login"))
    
    tid = tenant_id()
    try:
        # Get all active trucks (physical vehicles)
        trucks = db.session.query(Truck).filter(
            Truck.tenant_id == tid,
            Truck.active.is_(True)
        ).order_by(Truck.created_at.desc()).all()
        
        truck_list = []
        for truck in trucks:
            truck_list.append({
                "truck_id": truck.truck_id,
                "name": truck.name,
                "color": truck.color or '-',
                "truck_type": truck.truck_type.value if truck.truck_type else '-',
                "capacity": truck.capacity or '-',
                "license_plate": truck.license_plate or '-',
                "purchase_date": truck.purchase_date
            })
    except Exception as e:
        current_app.logger.exception(f"Error fetching trucks: {e}")
        truck_list = []
    
    # Get truck types for dropdown
    truck_types = [{"value": t.name, "label": t.value} for t in TruckType]
    
    return render_template("trucks.html", trucks=truck_list, truck_types=truck_types)


@main.route("/truck/<int:truck_id>/delete", methods=["POST"])
def delete_truck(truck_id):
    """Delete a truck (set inactive)."""
    if "employee_id" not in session:
        flash("Log in om trucks te verwijderen.", "error")
        return redirect(url_for("main.login"))
    
    tid = tenant_id()
    try:
        # Find the truck
        truck = Truck.query.filter_by(tenant_id=tid, truck_id=truck_id).first()
        if not truck:
            flash("Truck niet gevonden.", "error")
            return redirect(url_for("main.trucks_list"))
        
        # Set truck to inactive instead of deleting
        truck.active = False
        db.session.commit()
        flash(f"Truck '{truck.name}' is verwijderd.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting truck: {e}")
        flash("Kon truck niet verwijderen.", "error")
    
    return redirect(url_for("main.trucks_list"))


# --- Drivers Management (Improved) ---
@main.route("/drivers", methods=["GET"])
def drivers_list():
    """Show all active drivers for current tenant with all their availability dates."""
    if "employee_id" not in session:
        return redirect(url_for("main.login"))
    
    tid = tenant_id()
    today = date.today()
    
    try:
        # First, get all active drivers
        all_drivers = db.session.query(Employee).filter(
            Employee.tenant_id == tid,
            Employee.role == EmployeeRole.driver,
            Employee.active.is_(True)
        ).order_by(Employee.last_name.asc()).all()
        
        driver_list = []
        
        # For each driver, get all their availability dates
        for driver in all_drivers:
            # Get all availability dates for this driver (current and future)
            availabilities = db.session.query(Availability).filter(
                Availability.tenant_id == tid,
                Availability.employee_id == driver.employee_id,
                Availability.active.is_(True),
                Availability.available_date >= today
            ).order_by(Availability.available_date.asc()).all()
            
            # Format all available dates
            available_dates = [av.available_date.strftime('%d-%m-%Y') for av in availabilities]
            
            # Check if available today - explicitly check if there's an availability record for today
            # Convert both to date objects to ensure correct comparison
            available_today = False
            for av in availabilities:
                # Ensure we compare date objects (not datetime)
                av_date = av.available_date
                if isinstance(av_date, datetime):
                    av_date = av_date.date()
                if av_date == today:
                    available_today = True
                    break
            
            # Get the first future availability date for display
            first_available_date = available_dates[0] if available_dates else None
            
            driver_list.append({
                "employee_id": driver.employee_id,
                "name": f"{driver.first_name} {driver.last_name}",
                "email": driver.email,
                "available_date": first_available_date,
                "available_dates": available_dates,
                "available_today": available_today
            })
    except Exception as e:
        current_app.logger.exception(f"Error fetching drivers: {e}")
        driver_list = []
    
    return render_template("drivers.html", drivers=driver_list)


@main.route("/driver/<int:employee_id>/delete", methods=["POST"])
def delete_driver(employee_id):
    """Delete a driver (set inactive)."""
    if "employee_id" not in session:
        flash("Log in om chauffeurs te verwijderen.", "error")
        return redirect(url_for("main.login"))
    
    tid = tenant_id()
    try:
        # Find the driver
        driver = Employee.query.filter_by(
            tenant_id=tid, employee_id=employee_id, role=EmployeeRole.driver
        ).first()
        
        if not driver:
            flash("Chauffeur niet gevonden.", "error")
            return redirect(url_for("main.drivers_list"))
        
        # Set driver to inactive instead of deleting
        driver.active = False
        db.session.commit()
        flash(f"Chauffeur {driver.first_name} {driver.last_name} verwijderd.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting driver: {e}")
        flash("Kon chauffeur niet verwijderen.", "error")
    
    return redirect(url_for("main.drivers_list"))


# --- Truck Management (Physical Vehicles) ---
@main.route("/add-truck", methods=["POST"])
def add_truck():
    """Add a new physical truck with all details."""
    if "employee_id" not in session:
        return redirect(url_for("main.login"))
    
    tid = tenant_id()
    
    # Get form data
    name = request.form.get("name", "").strip()
    color = request.form.get("color", "").strip()
    truck_type_str = request.form.get("truck_type", "").strip()
    capacity = request.form.get("capacity", "").strip()
    license_plate = request.form.get("license_plate", "").strip()
    purchase_date_str = request.form.get("purchase_date", "").strip()
    
    if not name:
        flash("Vul de naam van de truck in (Merk & Model).", "error")
        return redirect(url_for("main.trucks_list"))
    
    try:
        # Parse truck type
        truck_type = None
        if truck_type_str:
            try:
                truck_type = TruckType[truck_type_str]
            except KeyError:
                truck_type = TruckType.bestelwagen
        
        # Parse purchase date
        purchase_date = None
        if purchase_date_str:
            try:
                purchase_date = datetime.strptime(purchase_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        
        # Check for duplicate license plate
        if license_plate:
            existing = Truck.query.filter_by(tenant_id=tid, license_plate=license_plate, active=True).first()
            if existing:
                flash(f"Er bestaat al een truck met nummerplaat {license_plate}.", "error")
                return redirect(url_for("main.trucks_list"))
        
        # Create new truck
        truck_id = get_next_truck_id(tid)
        truck = Truck(
            tenant_id=tid,
            truck_id=truck_id,
            name=name,
            color=color or None,
            truck_type=truck_type,
            capacity=capacity or None,
            license_plate=license_plate or None,
            purchase_date=purchase_date,
            active=True
        )
        db.session.add(truck)
        db.session.commit()
        
        flash(f"Truck '{name}' succesvol toegevoegd.", "success")
        current_app.logger.info(f"Added truck: {name} ({license_plate})")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error adding truck: {e}")
        flash("Fout bij het toevoegen van truck.", "error")
    
    return redirect(url_for("main.trucks_list"))


# ========== iCAL EXPORT ENDPOINTS ==========

@main.route("/export/deliveries.ics", methods=["GET"])
def export_deliveries_ical():
    """
    Exporteer alle geplande leveringen als iCal bestand.
    Kan gefilterd worden op datum range.
    """
    from .utils.ical import create_delivery_ical
    from flask import Response
    import traceback
    
    try:
        if "employee_id" not in session:
            current_app.logger.warning("Export iCal: User not logged in")
            # Return lege calendar in plaats van redirect (voor download flow)
            from icalendar import Calendar
            cal = Calendar()
            cal.add('prodid', '-//Sleep Inn Scheduler//sleepinn.be//')
            cal.add('version', '2.0')
            cal.add('calscale', 'GREGORIAN')
            cal.add('method', 'PUBLISH')
            ical_content = cal.to_ical()
            if not isinstance(ical_content, bytes):
                ical_content = ical_content.encode('utf-8')
            response = Response(ical_content, mimetype='text/calendar; charset=utf-8')
            response.headers['Content-Type'] = 'text/calendar; charset=utf-8'
            response.headers['Content-Disposition'] = 'attachment; filename=leveringen.ics'
            return response
        
        tid = tenant_id()
        current_app.logger.info(f"Export iCal: Starting for tenant {tid}")
        
        # Optionele filters
        start_date_str = request.args.get("start")
        end_date_str = request.args.get("end")
        
        # Haal leveringen op met betere error handling
        try:
            query = db.session.query(
                Delivery.delivery_id,
                Delivery.delivery_status,
                CustomerOrder.order_id,
                Region.name.label('region_name'),
                DeliveryRun.scheduled_date,
                Location.address
            ).outerjoin(
                DeliveryRun,
                (Delivery.tenant_id == DeliveryRun.tenant_id) & (Delivery.run_id == DeliveryRun.run_id)
            ).outerjoin(
                Region,
                (DeliveryRun.tenant_id == Region.tenant_id) & (DeliveryRun.region_id == Region.region_id)
            ).outerjoin(
                CustomerOrder,
                (Delivery.tenant_id == CustomerOrder.tenant_id) & (Delivery.order_id == CustomerOrder.order_id)
            ).outerjoin(
                Location,
                (CustomerOrder.tenant_id == Location.tenant_id) & (CustomerOrder.location_id == Location.location_id)
            ).filter(
                Delivery.tenant_id == tid
            )
            
            # Filter op datum als opgegeven
            if start_date_str:
                try:
                    start_date = date.fromisoformat(start_date_str)
                    query = query.filter(DeliveryRun.scheduled_date >= start_date)
                except ValueError:
                    current_app.logger.warning(f"Invalid start_date format: {start_date_str}")
                    pass
            
            if end_date_str:
                try:
                    end_date = date.fromisoformat(end_date_str)
                    query = query.filter(DeliveryRun.scheduled_date <= end_date)
                except ValueError:
                    current_app.logger.warning(f"Invalid end_date format: {end_date_str}")
                    pass
            
            rows = query.order_by(DeliveryRun.scheduled_date.asc()).all()
            current_app.logger.info(f"Export iCal: Found {len(rows)} deliveries")
            
        except Exception as query_error:
            current_app.logger.error(f"Error querying deliveries: {query_error}")
            current_app.logger.error(traceback.format_exc())
            rows = []
        
        deliveries = []
        for row in rows:
            try:
                # Haal product_description op
                product_description = None
                if row.order_id:
                    try:
                        order_item = db.session.query(OrderItem).filter_by(
                            tenant_id=tid, order_id=row.order_id
                        ).first()
                        if order_item and order_item.product_id:
                            product = Product.query.filter_by(
                                tenant_id=tid, product_id=order_item.product_id
                            ).first()
                            if product:
                                product_description = product.name
                    except Exception as product_error:
                        current_app.logger.warning(f"Error fetching product for order {row.order_id}: {product_error}")
                        product_description = None
                
                deliveries.append({
                    "delivery_id": row.delivery_id or 0,
                    "order_id": row.order_id,
                    "product_description": product_description,
                    "region_name": row.region_name or "Onbekend",
                    "scheduled_date": row.scheduled_date,
                    "address": row.address or "",
                    "status": row.delivery_status
                })
            except Exception as row_error:
                current_app.logger.warning(f"Error processing delivery row: {row_error}")
                continue
        
        current_app.logger.info(f"Export iCal: Processed {len(deliveries)} deliveries")
        
        # Genereer iCal - zorg dat dit altijd werkt, ook met lege lijst
        try:
            ical_content = create_delivery_ical(deliveries, "Delivery Schedule - Leveringen")
            current_app.logger.info("Export iCal: Successfully generated iCal content")
        except Exception as ical_error:
            current_app.logger.error(f"Error creating iCal: {ical_error}")
            current_app.logger.error(traceback.format_exc())
            # Fallback: maak een minimale geldige iCal
            from icalendar import Calendar
            cal = Calendar()
            cal.add('prodid', '-//Sleep Inn Scheduler//sleepinn.be//')
            cal.add('version', '2.0')
            cal.add('calscale', 'GREGORIAN')
            cal.add('method', 'PUBLISH')
            cal.add('x-wr-calname', 'Sleep Inn - Leveringen')
            ical_content = cal.to_ical()
            if not isinstance(ical_content, bytes):
                ical_content = ical_content.encode('utf-8')
        
        # Return als downloadbaar .ics bestand
        # Dit werkt het beste voor Google Calendar import (via bestand upload)
        response = Response(ical_content, mimetype='text/calendar; charset=utf-8')
        response.headers['Content-Type'] = 'text/calendar; charset=utf-8'
        response.headers['Content-Disposition'] = 'attachment; filename=leveringen.ics'
        
        return response
        
    except Exception as e:
        current_app.logger.exception(f"Error exporting deliveries to iCal: {e}")
        current_app.logger.error(traceback.format_exc())
        # Return een minimale geldige iCal in plaats van error (voor download flow)
        try:
            from icalendar import Calendar
            cal = Calendar()
            cal.add('prodid', '-//Sleep Inn Scheduler//sleepinn.be//')
            cal.add('version', '2.0')
            cal.add('calscale', 'GREGORIAN')
            cal.add('method', 'PUBLISH')
            cal.add('x-wr-calname', 'Sleep Inn - Leveringen')
            ical_content = cal.to_ical()
            if not isinstance(ical_content, bytes):
                ical_content = ical_content.encode('utf-8')
        except Exception as fallback_error:
            current_app.logger.error(f"Even fallback iCal failed: {fallback_error}")
            # Laatste redmiddel: return een minimale geldige iCal string
            ical_content = b'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Sleep Inn Scheduler//sleepinn.be//\r\nCALSCALE:GREGORIAN\r\nMETHOD:PUBLISH\r\nEND:VCALENDAR\r\n'
        
        response = Response(ical_content, mimetype='text/calendar; charset=utf-8')
        response.headers['Content-Type'] = 'text/calendar; charset=utf-8'
        response.headers['Content-Disposition'] = 'attachment; filename=leveringen.ics'
        return response


@main.route("/export/driver/<int:employee_id>/schedule.ics", methods=["GET"])
def export_driver_schedule_ical(employee_id):
    """
    Exporteer het leveringsschema van een specifieke chauffeur als iCal.
    """
    from .utils.ical import create_driver_schedule_ical
    from flask import Response
    
    if "employee_id" not in session:
        return redirect(url_for("main.login"))
    
    tid = tenant_id()
    
    try:
        # Haal chauffeur info op
        driver = Employee.query.filter_by(
            tenant_id=tid, 
            employee_id=employee_id,
            role=EmployeeRole.driver
        ).first()
        
        if not driver:
            flash("Chauffeur niet gevonden.", "error")
            return redirect(url_for("main.drivers_list"))
        
        driver_name = f"{driver.first_name} {driver.last_name}"
        
        # Haal leveringen op waar deze chauffeur aan gekoppeld is
        rows = db.session.query(
            Delivery.delivery_id,
            CustomerOrder.order_id,
            Region.name.label('region_name'),
            DeliveryRun.scheduled_date,
            Location.address
        ).join(
            DeliveryRun,
            (Delivery.tenant_id == DeliveryRun.tenant_id) & (Delivery.run_id == DeliveryRun.run_id)
        ).outerjoin(
            Region,
            (DeliveryRun.tenant_id == Region.tenant_id) & (DeliveryRun.region_id == Region.region_id)
        ).outerjoin(
            CustomerOrder,
            (Delivery.tenant_id == CustomerOrder.tenant_id) & (Delivery.order_id == CustomerOrder.order_id)
        ).outerjoin(
            Location,
            (CustomerOrder.tenant_id == Location.tenant_id) & (CustomerOrder.location_id == Location.location_id)
        ).filter(
            DeliveryRun.tenant_id == tid,
            DeliveryRun.driver_id == employee_id,
            DeliveryRun.scheduled_date >= date.today()
        ).order_by(DeliveryRun.scheduled_date.asc()).all()
        
        deliveries = []
        for row in rows:
            deliveries.append({
                "delivery_id": row.delivery_id,
                "order_id": row.order_id,
                "region_name": row.region_name or "Onbekend",
                "scheduled_date": row.scheduled_date,
                "address": row.address
            })
        
        # Haal beschikbaarheidsdagen op
        avail_rows = Availability.query.filter(
            Availability.tenant_id == tid,
            Availability.employee_id == employee_id,
            Availability.available_date >= date.today(),
            Availability.active.is_(True)
        ).order_by(Availability.available_date.asc()).all()
        
        availability_dates = [a.available_date for a in avail_rows]
        
        # Genereer iCal
        ical_content = create_driver_schedule_ical(driver_name, deliveries, availability_dates)
        
        # Return als downloadbaar bestand
        filename = f"leveringen-{driver.first_name.lower()}-{driver.last_name.lower()}.ics"
        response = Response(ical_content, mimetype='text/calendar')
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response
        
    except Exception as e:
        current_app.logger.exception(f"Error exporting driver schedule to iCal: {e}")
        flash("Kon schema niet exporteren.", "error")
        return redirect(url_for("main.drivers_list"))


@main.route("/export/my-schedule.ics", methods=["GET"])
def export_my_schedule_ical():
    """
    Exporteer het schema van de ingelogde gebruiker (als chauffeur).
    """
    if "employee_id" not in session:
        return redirect(url_for("main.login"))
    
    return redirect(url_for("main.export_driver_schedule_ical", employee_id=session["employee_id"]))


# --- Region Settings API ---
@main.route("/api/region-settings", methods=["GET"])
def get_region_settings():
    """
    Haal de huidige regio-instellingen op (tenant defaults).
    """
    if "employee_id" not in session:
        return jsonify({"error": "Niet ingelogd"}), 401
    
    tid = tenant_id()
    tenant = Tenant.query.get(tid)
    
    if not tenant:
        return jsonify({"error": "Tenant niet gevonden"}), 404
    
    return jsonify({
        "radius_km": tenant.default_radius_km or 30.0,
        "max_deliveries_per_day": tenant.default_max_deliveries or 13
    })


@main.route("/api/region-settings", methods=["POST"])
def update_region_settings():
    """
    Update de regio-instellingen (tenant defaults).
    Kan ook alle bestaande regio's bijwerken indien gewenst.
    """
    if "employee_id" not in session:
        return jsonify({"error": "Niet ingelogd"}), 401
    
    tid = tenant_id()
    tenant = Tenant.query.get(tid)
    
    if not tenant:
        return jsonify({"error": "Tenant niet gevonden"}), 404
    
    data = request.get_json() or {}
    
    # Valideer waarden
    radius_km = data.get("radius_km")
    max_deliveries = data.get("max_deliveries_per_day")
    update_existing = data.get("update_existing_regions", False)
    
    if radius_km is not None:
        try:
            radius_km = float(radius_km)
            if radius_km < 1 or radius_km > 500:
                return jsonify({"error": "Straal moet tussen 1 en 500 km zijn"}), 400
            tenant.default_radius_km = radius_km
        except (ValueError, TypeError):
            return jsonify({"error": "Ongeldige straal waarde"}), 400
    
    if max_deliveries is not None:
        try:
            max_deliveries = int(max_deliveries)
            if max_deliveries < 1 or max_deliveries > 100:
                return jsonify({"error": "Max leveringen moet tussen 1 en 100 zijn"}), 400
            tenant.default_max_deliveries = max_deliveries
        except (ValueError, TypeError):
            return jsonify({"error": "Ongeldige max leveringen waarde"}), 400
    
    # Update ook alle bestaande regio's indien gewenst
    if update_existing:
        regions = Region.query.filter_by(tenant_id=tid).all()
        for region in regions:
            if radius_km is not None:
                region.radius_km = radius_km
            if max_deliveries is not None:
                region.max_deliveries_per_day = max_deliveries
    
    db.session.commit()
    
    return jsonify({
        "success": True,
        "radius_km": tenant.default_radius_km,
        "max_deliveries_per_day": tenant.default_max_deliveries,
        "regions_updated": len(regions) if update_existing else 0
    })
