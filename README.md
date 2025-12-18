[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/DxqGQVx4)
# Sleep Inn Scheduler — Functies

Korte beschrijving van wat je op de site kunt doen.

## Hoofdschermen
- Home: dashboard met navigatie naar bestellingen, runs, chauffeurs en trucks.
- Inloggen/Registreren: accounts aanmaken en inloggen.
- Leveringen: leveringen met bijbehorende producten en datums beheren.
- Nieuwe levering: handmatig een product en levering toevoegen.
- Trucks: voertuigen bekijken en beheren.
- Drivers: chauffeurs en bijchauffeurs bekijken, toevoegen, beschikbaarheid beheren.

## Bestellingen en leveringen
- Orders aanmaken vanuit leveringen of het formulier op `/add-listing`.
- Automatisch demo-klant en demo-locatie aanmaken als ze nog ontbreken.
- Levering plannen: koppelt een order aan een regio, datum, chauffeur (indien beschikbaar).
- Capaciteitscontrole per delivery run (max aantal stops).
- Statussen: orders (new/in_progress/completed/cancelled) en deliveries (scheduled/delivered/cancelled).

## Regio’s en locaties
- Regio’s per tenant met straal en max leveringen.
- Locaties gekoppeld aan regio’s; demo “Demo Store” wordt automatisch aangemaakt.

## Chauffeurs en beschikbaarheid
- Rollen: seller, driver, helper, manager, admin.
- Beschikbaarheid per datum vastleggen; koppelen aan runs bij plannen.

## Voertuigen
- Trucks met type, kleur, capaciteit, kenteken.
- Unieke kentekens per tenant.

## Multi-tenant basis
- `tenant_id` op alle tabellen; default tenant wordt bij start of eerste run aangemaakt.

## Tech stack
-Hoofdstack (server + data):
  -Flask 3.1 (Python) met Jinja2 templates.
  -Flask-SQLAlchemy + SQLAlchemy 2.0 voor ORM.
  -Flask-Migrate/Alembic voor schema migraties.
  -Database primair: PostgreSQL (Supabase), lokaal fallback: SQLite.
  -psycopg2-binary als Postgres driver.
-Frontend:
  -Server-side rendered HTML + Jinja2.
  -Statische assets (CSS/JS) onder app/static; geen React of bundler.
-Overige:
  -Requests voor HTTP-calls, icalendar util.
  -Mapbox token support voor geolocatie in templates (config).

## UI prototype (Figma)

## Database

## User stories

## Feedback sessions

## Team
- Alexia Lehouck
- Pierre Broekaert
- Herben Vanderhaegen
- Michael Vandekerckhove
- Arnaud Jaecques
