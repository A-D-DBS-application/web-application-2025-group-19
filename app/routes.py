
# app/routes.py
import os
import requests
from datetime import date, timedelta, datetime
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, jsonify
from .models import (
    db, Tenant, Region, Location, Employee, Availability, Customer, Product,
    CustomerOrder, OrderItem, DeliveryRun, Delivery, RegionAddress,
    EmployeeRole, RunStatus, set_employee_availability, get_available_drivers, add_order,
    upsert_run_and_attach_delivery_with_capacity, get_delivery_overview, suggest_delivery_days,
    find_matching_regions, get_suggested_dates_for_address, add_address_to_region,
    create_new_region_with_address, count_deliveries_for_region_date, haversine_distance
)

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
        ).filter(
            Delivery.tenant_id == tid,
            Delivery.delivery_status == 'scheduled'
        ).order_by(DeliveryRun.scheduled_date.asc()).limit(12).all()
        
        # Convert to dict format for template
        upcoming_deliveries = [
            {
                "delivery_id": d_id,
                "order_id": o_id,
                "municipality": region_name or 'N/A',
                "delivery_status": str(status).split('.')[-1] if status else 'unknown'
            }
            for d_id, o_id, region_name, status in upcoming_deliveries
        ]
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
                # Unpack: delivery_id, product_id, region_name, status, order_date, scheduled_date, region_id
                d_id, p_id, region_name, status, order_date, sched_date, r_id = row

                # Build display info - show product_id instead of order_id
                items.append({
                    "delivery_id": d_id,
                    "product_id": p_id,
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


@main.route("/drivers", methods=["GET"])
def drivers():
    # Show available drivers for the current tenant
    if "employee_id" not in session:
        return redirect(url_for("main.login"))

    tid = tenant_id()
    try:
        drivers_list = db.session.query(Employee).filter(
            Employee.tenant_id == tid,
            Employee.role == EmployeeRole.driver,
            Employee.active.is_(True)
        ).order_by(Employee.last_name.asc()).all()
    except Exception as e:
        current_app.logger.exception(f"Failed to query drivers for drivers overview: {e}")
        drivers_list = []

    return render_template("drivers.html", drivers=drivers_list)

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

    from .models import get_next_employee_id
    next_emp_id = get_next_employee_id(tid)
    
    emp = Employee(
        tenant_id=tid, employee_id=next_emp_id, first_name=first, last_name=last,
        email=email, role=EmployeeRole.seller, active=True
    )
    db.session.add(emp)
    db.session.flush()  # krijg id (auto-increment)
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
    availability_date_str = request.form.get("availability_date", "").strip()

    if not first or not last or not email:
        flash("Vul voornaam, achternaam en e-mail in.", "error")
        return redirect(url_for("main.index"))

    tid = tenant_id()
    # Prevent duplicates by email
    if Employee.query.filter_by(tenant_id=tid, email=email).first():
        flash("E-mailadres bestaat al voor een medewerker.", "error")
        return redirect(url_for("main.index"))

    try:
        next_emp_id = get_next_employee_id(tid)
        emp = Employee(
            tenant_id=tid, employee_id=next_emp_id, first_name=first, last_name=last, email=email,
            role=EmployeeRole.driver, active=True
        )
        db.session.add(emp)
        db.session.flush()  # Get the id before commit
        
        # Set availability based on user input or use today as default
        if availability_date_str:
            try:
                availability_date = datetime.strptime(availability_date_str, "%Y-%m-%d").date()
            except ValueError:
                availability_date = date.today()
        else:
            availability_date = date.today()
        
        try:
            set_employee_availability(tid, emp.employee_id, availability_date, active=True)
            current_app.logger.info(f"Added driver {first} {last} with availability for {availability_date}")
        except Exception as e:
            current_app.logger.exception(f"Failed to set availability for new driver: {e}")
            # Still commit the driver even if availability fails
            db.session.commit()
            flash(f"Chauffeur {first} {last} toegevoegd, maar beschikbaarheid kon niet worden ingesteld.", "warning")
            return redirect(url_for("main.index"))
        
        db.session.commit()
        flash(f"Chauffeur {first} {last} toegevoegd en beschikbaar gemaakt voor {availability_date.strftime('%d-%m-%Y')}.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error adding driver: {e}")
        flash("Fout bij het toevoegen van chauffeur.", "error")
    
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
    address = request.form.get("address")
    region_name = request.form.get("region_id")  # Municipality name (optional)
    scheduled_date_str = request.form.get("scheduled_date")
    
    # Coördinaten uit hidden fields (gezet door frontend via Mapbox)
    lat_str = request.form.get("lat", "")
    lng_str = request.form.get("lng", "")
    selected_region_id = request.form.get("selected_region_id", "")

    try:
        order_id = int(order_id)
        scheduled_date = date.fromisoformat(scheduled_date_str)
    except Exception:
        flash("Ongeldige invoer.", "error")
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
                        region_name_new = region_name or f"Regio {scheduled_date.strftime('%d-%m-%Y')}"
                        region_id, _ = create_new_region_with_address(tid, region_name_new, address, lat, lng, scheduled_date)
                        current_app.logger.info(f"Created new region {region_id} (all nearby regions full)")
                else:
                    # Voeg adres toe aan bestaande regio
                    add_address_to_region(tid, region_id, address, lat, lng, scheduled_date)
                    current_app.logger.info(f"Added address to nearest region {region_id}")
            else:
                # Geen bestaande regio binnen 30km, maak nieuwe regio
                region_name_new = region_name or f"Regio {scheduled_date.strftime('%d-%m-%Y')}"
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

    # Ensure the order exists; if user typed an ID that doesn't exist, create a demo order
    try:
        existing_order = CustomerOrder.query.filter_by(tenant_id=tid, order_id=order_id).first()
    except Exception:
        existing_order = None

    if not existing_order:
        try:
            # create demo customer/location if needed
            customer = Customer.query.filter_by(tenant_id=tid, email="demo@customer.local").first()
            if not customer:
                from .models import get_next_customer_id
                customer_id = get_next_customer_id(tid)
                customer = Customer(tenant_id=tid, customer_id=customer_id, name="Demo Customer", municipality="DemoTown", email="demo@customer.local")
                db.session.add(customer); db.session.flush()

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

            # create a new order for this demo product
            new_order_id = add_order(tenant_id=tid, customer_id=customer.customer_id, location_id=loc.location_id, seller_id=session["employee_id"], product_name=f"Imported {order_id}")
            order_id = int(new_order_id)
            current_app.logger.info(f"Created demo order {order_id} for scheduling (input product id).")
        except Exception:
            current_app.logger.exception("Failed to create demo order for schedule request")
            flash("Kon geen order aanmaken voor deze levering.", "error")
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


# --- Truck Management ---
@main.route("/trucks", methods=["GET"])
def trucks_list():
    """Show all active trucks/routes for current tenant."""
    if "employee_id" not in session:
        return redirect(url_for("main.login"))
    
    tid = tenant_id()
    try:
        # Get all planned runs (trucks) for this tenant
        trucks = db.session.query(DeliveryRun).filter(
            DeliveryRun.tenant_id == tid,
            DeliveryRun.status == RunStatus.planned
        ).order_by(DeliveryRun.scheduled_date.desc()).all()
        
        truck_list = []
        for truck in trucks:
            # Count deliveries on this run
            delivery_count = db.session.query(db.func.count(Delivery.delivery_id)).filter(
                Delivery.tenant_id == tid,
                Delivery.run_id == truck.run_id
            ).scalar() or 0
            
            # Get region name
            region = db.session.query(Region).filter_by(
                tenant_id=tid, region_id=truck.region_id
            ).first()
            
            # Get driver name if assigned
            driver_name = None
            if truck.driver_id:
                driver = db.session.query(Employee).filter_by(
                    tenant_id=tid, employee_id=truck.driver_id
                ).first()
                if driver:
                    driver_name = f"{driver.first_name} {driver.last_name}"
            
            truck_list.append({
                "run_id": truck.run_id,
                "region": region.name if region else 'Niet ingesteld',
                "scheduled_date": truck.scheduled_date,
                "driver_id": truck.driver_id,
                "driver_name": driver_name or 'Niet toegewezen',
                "capacity": truck.capacity,
                "delivery_count": delivery_count
            })
    except Exception as e:
        current_app.logger.exception(f"Error fetching trucks: {e}")
        truck_list = []
    
    return render_template("trucks.html", trucks=truck_list)


@main.route("/truck/<int:run_id>/delete", methods=["POST"])
def delete_truck(run_id):
    """Delete a truck (delivery run) and all associated deliveries."""
    if "employee_id" not in session:
        flash("Log in om trucks te verwijderen.", "error")
        return redirect(url_for("main.login"))
    
    tid = tenant_id()
    try:
        # Find the delivery run
        run = DeliveryRun.query.filter_by(tenant_id=tid, run_id=run_id).first()
        if not run:
            flash("Truck niet gevonden.", "error")
            return redirect(url_for("main.trucks_list"))
        
        # Delete all deliveries associated with this run first
        Delivery.query.filter_by(tenant_id=tid, run_id=run_id).delete()
        
        # Then delete the run itself
        db.session.delete(run)
        db.session.commit()
        flash(f"Truck op {run.scheduled_date} is verwijderd.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting truck: {e}")
        flash("Kon truck niet verwijderen.", "error")
    
    return redirect(url_for("main.trucks_list"))


# --- Drivers Management (Improved) ---
@main.route("/drivers", methods=["GET"])
def drivers_list():
    """Show all active drivers for current tenant with availability info."""
    if "employee_id" not in session:
        return redirect(url_for("main.login"))
    
    tid = tenant_id()
    today = date.today()
    
    try:
        # Get all active drivers with their availability info
        drivers = db.session.query(
            Employee.employee_id,
            Employee.first_name,
            Employee.last_name,
            Employee.email,
            Availability.available_date,
            Availability.active.label('is_available')
        ).outerjoin(
            Availability,
            (Employee.employee_id == Availability.employee_id) & (Availability.available_date >= today)
        ).filter(
            Employee.tenant_id == tid,
            Employee.role == EmployeeRole.driver,
            Employee.active.is_(True)
        ).order_by(Employee.last_name.asc(), Availability.available_date.asc()).all()
        
        driver_list = []
        seen_ids = set()  # To avoid duplicates
        for row in drivers:
            emp_id = row.employee_id
            if emp_id not in seen_ids:
                seen_ids.add(emp_id)
                driver_list.append({
                    "employee_id": emp_id,
                    "name": f"{row.first_name} {row.last_name}",
                    "email": row.email,
                    "available_date": row.available_date.strftime('%d-%m-%Y') if row.available_date else 'Niet ingesteld',
                    "available_today": row.is_available and row.available_date == today if row.available_date else False
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


# --- Truck Management ---
@main.route("/add-truck", methods=["POST"])
def add_truck():
    """Add a new truck (delivery run) with specified date and capacity."""
    if "employee_id" not in session:
        return redirect(url_for("main.login"))
    
    tid = tenant_id()
    scheduled_date_str = request.form.get("scheduled_date", "").strip()
    capacity_str = request.form.get("capacity", "").strip()
    
    if not scheduled_date_str or not capacity_str:
        flash("Selecteer alstublieft een datum en voer capaciteit in.", "error")
        return redirect(url_for("main.index"))
    
    try:
        scheduled_date = datetime.strptime(scheduled_date_str, "%Y-%m-%d").date()
        capacity = int(capacity_str)
        
        if capacity <= 0:
            raise ValueError("Capaciteit moet groter dan 0 zijn.")
        
        # Create new delivery run (truck)
        run = DeliveryRun(
            tenant_id=tid,
            scheduled_date=scheduled_date,
            capacity=capacity,
            status=RunStatus.planned
        )
        db.session.add(run)
        db.session.commit()
        
        flash(f"Truck toegevoegd voor {scheduled_date.strftime('%d-%m-%Y')} met capaciteit {capacity}.", "success")
        current_app.logger.info(f"Added truck for {scheduled_date} with capacity {capacity}")
    except ValueError as e:
        current_app.logger.error(f"Invalid input for truck: {e}")
        flash(f"Ongeldige invoer: {e}", "error")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error adding truck: {e}")
        flash("Fout bij het toevoegen van truck.", "error")
    
    return redirect(url_for("main.index"))
