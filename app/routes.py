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
)

main = Blueprint("main", __name__)

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
