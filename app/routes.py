<<<<<<< HEAD


# app/routes.py
from datetime import date
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from .models import (
    db, Tenant, Region, Location, Employee, Availability, Customer, Product,
    CustomerOrder, OrderItem, DeliveryRun, Delivery,
    EmployeeRole, set_employee_availability, get_available_drivers, add_order,
    upsert_run_and_attach_delivery, get_delivery_overview, suggest_delivery_days
=======
# app/routes.py
from datetime import datetime, date as date_cls, time as time_cls
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from .models import (
    db, Medewerker, Beschikbaarheid, Product, Levering,
    set_medewerker_beschikbaarheid_global,
    set_medewerker_beschikbaarheid_op_dag,
    get_beschikbare_chauffeurs, create_levering,
    get_levering_overview, suggest_delivery_days_by_municipality,
    extract_municipality_from_adres, gebruikte_minuten_op_dag, werkdag_minuten,
>>>>>>> fa763f594a89d16781ff5dc80a17f22ecaa38367
)

main = Blueprint("main", __name__)

<<<<<<< HEAD
def tenant_id() -> int:
    return int(current_app.config.get("TENANT_ID", 1))

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

    if Employee.query.filter_by(tenant_id=tenant_id(), email=email).first():
        flash("E-mailadres bestaat al.", "error")
        return redirect(url_for("main.register"))

    emp = Employee(
        tenant_id=tenant_id(), first_name=first, last_name=last,
        email=email, role=EmployeeRole.seller, active=True
    )
    db.session.add(emp)
    db.session.commit()

    session["employee_id"] = emp.employee_id
    session["username"] = f"{emp.first_name}.{emp.last_name}".lower()
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
    emp = (Employee.query
           .filter_by(tenant_id=tenant_id(), first_name=first, last_name=last, active=True)
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

    # Demo customer/location — vervang later met echte UI-selecties
    customer = Customer.query.filter_by(tenant_id=tenant_id(), email="demo@customer.local").first()
    if not customer:
        customer = Customer(tenant_id=tenant_id(), name="Demo Customer", municipality="DemoTown",
                            email="demo@customer.local")
        db.session.add(customer); db.session.flush()

    loc = Location.query.filter_by(tenant_id=tenant_id(), name="Demo Store").first()
    if not loc:
        loc = Location(tenant_id=tenant_id(), name="Demo Store", address="Demo Street 1", region_id=None)
        db.session.add(loc); db.session.flush()

    order_id = add_order(
        tenant_id=tenant_id(),
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
    days = suggest_delivery_days(tenant_id(), region_id)
    flash(f"Voorgestelde dagen voor regio {region_id}: {', '.join(map(str, days)) or 'geen'}", "info")
    return redirect(url_for("main.index"))

# --- Levering plannen ---
@main.route("/schedule", methods=["POST"])
def schedule():
    if "employee_id" not in session:
        flash("Log in om leveringen te plannen.", "error")
        return redirect(url_for("main.login"))

    order_id = int(request.form.get("order_id"))
    region_id = request.form.get("region_id")
    scheduled_date_str = request.form.get("scheduled_date")

    try:
        region_id = int(region_id) if region_id else None
        scheduled_date = date.fromisoformat(scheduled_date_str)
    except Exception:
        flash("Ongeldige invoer.", "error")
        return redirect(url_for("main.index"))

    drivers = get_available_drivers(tenant_id(), region_id, scheduled_date) if region_id else []
    driver_id = drivers[0].employee_id if drivers else None

    delivery_id = upsert_run_and_attach_delivery(tenant_id(), order_id, region_id, driver_id, scheduled_date)
    flash(f"Levering #{delivery_id} gepland op {scheduled_date}.", "success")
    return redirect(url_for("main.index"))
=======
# ---------------------
# Pages
# ---------------------
@main.route("/")
def index():
    # Simple landing: counts and today overview
    today = date_cls.today()
    chauffeurs = get_beschikbare_chauffeurs(today)
    overzicht = get_levering_overview(datum=today)
    return render_template("index.html", chauffeurs=chauffeurs, overzicht=overzicht, today=today)

# ---- Medewerkers ----
@main.route("/medewerkers")
def medewerkers_list():
    lijst = Medewerker.query.order_by(Medewerker.naam.asc()).all()
    return render_template("medewerkers.html", medewerkers=lijst)

@main.route("/medewerkers/nieuw", methods=["GET", "POST"])
def medewerkers_nieuw():
    if request.method == "POST":
        naam = (request.form.get("naam") or "").strip()
        rol = (request.form.get("rol") or "").strip().lower()
        if not naam or not rol:
            flash("Naam en rol zijn vereist.", "error")
            return redirect(url_for("main.medewerkers_nieuw"))
        m = Medewerker(naam=naam, rol=rol, beschikbaar=True)
        db.session.add(m)
        db.session.commit()
        flash("Medewerker toegevoegd.", "success")
        return redirect(url_for("main.medewerkers_list"))
    return render_template("medewerker_nieuw.html")

@main.route("/medewerkers/<int:mid>/beschikbaar", methods=["POST"])
def medewerkers_toggle(mid: int):
    beschikbaar = request.form.get("beschikbaar") == "true"
    set_medewerker_beschikbaarheid_global(mid, beschikbaar)
    flash("Globale beschikbaarheid bijgewerkt.", "success")
    return redirect(url_for("main.medewerkers_list"))

# ---- Beschikbaarheid per dag ----
@main.route("/beschikbaarheid", methods=["GET", "POST"])
def beschikbaarheid_view():
    today = date_cls.today()
    if request.method == "POST":
        mid = int(request.form.get("medewerker_id"))
        dag_str = request.form.get("datum")
        dag = datetime.strptime(dag_str, "%Y-%m-%d").date()
        beschikbaar = request.form.get("beschikbaar") == "true"
        set_medewerker_beschikbaarheid_op_dag(mid, dag, beschikbaar)
        flash("Beschikbaarheid per dag bijgewerkt.", "success")
        return redirect(url_for("main.beschikbaarheid_view"))

    # page data
    medewerkers = Medewerker.query.order_by(Medewerker.naam.asc()).all()
    # show last 30 records
    records = (
        Beschikbaarheid.query
        .order_by(Beschikbaarheid.datum.desc())
        .limit(30)
        .all()
    )
    return render_template("beschikbaarheid.html", medewerkers=medewerkers, records=records, today=today)

# ---- Leveringen toevoegen / plannen ----
@main.route("/levering/nieuw", methods=["GET", "POST"])
def levering_nieuw():
    if request.method == "POST":
        datum_str = request.form.get("datum")
        tijd_str = request.form.get("tijdstip")
        medewerker_id = request.form.get("medewerker_id")
        medewerker_id = int(medewerker_id) if medewerker_id else None
        product_naam = (request.form.get("product_naam") or "").strip()
        adres = (request.form.get("adres") or "").strip()
        handmatig = (request.form.get("handmatig") == "true")

        # Parse date/time
        try:
            datum = datetime.strptime(datum_str, "%Y-%m-%d").date()
        except Exception:
            flash("Ongeldige datum.", "error")
            return redirect(url_for("main.levering_nieuw"))

        tijdstip = None
        if tijd_str:
            try:
                tijdstip = datetime.strptime(tijd_str, "%H:%M").time()
            except Exception:
                flash("Ongeldig tijdstip (hh:mm).", "error")
                return redirect(url_for("main.levering_nieuw"))

        # If chauffeur chosen, validate capacity & availability; create levering
        try:
            levering_id = create_levering(
                datum=datum,
                tijdstip=tijdstip,
                medewerker_id=medewerker_id,
                product_naam=product_naam,
                adres=adres,
                handmatig=handmatig,
            )
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("main.levering_nieuw"))

        flash(f"Levering #{levering_id} aangemaakt.", "success")
        return redirect(url_for("main.leveringen_overzicht"))

    # GET: form datasets
    today = date_cls.today()
    chauffeurs_vandaag = get_beschikbare_chauffeurs(today)
    chauffeurs_morgen = get_beschikbare_chauffeurs(today.replace(day=today.day))  # simple reuse

    producten = Product.query.order_by(Product.naam.asc()).all()
    return render_template(
        "levering_nieuw.html",
        chauffeurs_vandaag=chauffeurs_vandaag,
        chauffeurs_morgen=chauffeurs_morgen,
        producten=producten,
        today=today,
        workday_minutes=werkdag_minuten(),
    )

# ---- Overzicht ----
@main.route("/leveringen")
def leveringen_overzicht():
    dag_str = request.args.get("datum")
    medewerker_id = request.args.get("medewerker_id")
    dag = datetime.strptime(dag_str, "%Y-%m-%d").date() if dag_str else None
    mid = int(medewerker_id) if medewerker_id else None

    overzicht = get_levering_overview(datum=dag, medewerker_id=mid)

    # aggregate per medewerker per dag (minutes used)
    totals = {}
    for row in overzicht:
        key = (row["medewerker_id"], row["datum"])
        totals[key] = totals.get(key, 0) + int(row["tijdslot_minuten"] or 0)

    return render_template("leveringen_overzicht.html", overzicht=overzicht, totals=totals, workday_minutes=werkdag_minuten())

# ---- Suggesties op basis van 'gemeente' uit adres ----
@main.route("/suggesties")
def suggesties():
    adres = request.args.get("adres", "")
    municipality = extract_municipality_from_adres(adres)
    days = suggest_delivery_days_by_municipality(municipality)
    return render_template("suggesties.html", adres=adres, municipality=municipality, days=days)

# ---------------------
# Lightweight JSON APIs
# ---------------------
@main.route("/api/chauffeurs")
def api_chauffeurs():
    dag_str = request.args.get("datum")
    dag = datetime.strptime(dag_str, "%Y-%m-%d").date() if dag_str else date_cls.today()
    return jsonify({"chauffeurs": [{"id": i, "naam": n} for (i, n) in get_beschikbare_chauffeurs(dag)]})

@main.route("/api/capacity")
def api_capacity():
    mid = int(request.args.get("medewerker_id"))
    dag = datetime.strptime(request.args.get("datum"), "%Y-%m-%d").date()
    used = gebruikte_minuten_op_dag(mid, dag)
    return jsonify({"used_minutes": used, "workday_minutes": werkdag_minuten(), "remaining": max(werkdag_minuten() - used, 0)})
>>>>>>> fa763f594a89d16781ff5dc80a17f22ecaa38367
