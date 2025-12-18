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

## Database
- PostgreSQL (Supabase) als primaire database; SQLite fallback mogelijk voor lokaal testen.

## Tech stack
- Backend: Flask 3.1 (Python) met Jinja2-templates.
- Data: SQLAlchemy 2.0 + Flask-SQLAlchemy; Flask-Migrate/Alembic voor schema-migraties.
- Database: PostgreSQL (Supabase) primair, SQLite lokaal als fallback; driver: psycopg2-binary.
- Frontend: server-side rendered HTML/Jinja2 met statische assets in `app/static`.
- Overig: requests voor HTTP-calls, icalendar helper, Mapbox token-support in config.

## Database artefacten
- ERD-model: (niet aangetroffen in de repo). Voeg bijv. toe in `docs/erd.png` of `assets/erd.png`.
- DDL-schema: (niet aangetroffen). Plaats bij voorkeur in `docs/schema.sql` of `migrations/` als referentie.
- Database dump/backup: (niet aangetroffen). Bewaar bij voorkeur buiten de repo of in `backups/` met naam en datum, bv. `backups/db-backup-YYYYMMDD.sql`.

## UI prototype (Figma)
- Figma prototype main UI: https://www.figma.com/make/wONpMO5WGtPqdMSlWbuxA9/Recreate-Website-Design?t=qzE7xTEhYC9LVvCJ-1
- Figma prototype Login: https://www.figma.com/make/JrogweV06uG5t0fhWOjKEk/Recreate-Login-Window?t=vCxRCXjFN6Bna2wM-1

## User stories

## Feedback sessions

## Team
- Alexia Lehouck
- Pierre Broekaert
- Herben Vanderhaegen
- Michael Vandekerckhove
- Arnaud Jaecques
