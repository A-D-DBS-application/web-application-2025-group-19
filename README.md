[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/DxqGQVx4)
# Sleep Inn Scheduler — Functies

## Wat is het doel?
- Projectbeschrijving: https://ugentbe-my.sharepoint.com/:w:/g/personal/arnaud_jaecques_ugent_be/IQAlcBniS3dkQ4pIevxqwnqsAfS2xTmEqggnpMmjvZuCLlI?e=g2rxez

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
- ERD-model: in ERD model.png (https://github.com/A-D-DBS-application/web-application-2025-group-19/blob/main/ERD%20model.png)
- Database dump/backup: in Database dump.docx (https://github.com/A-D-DBS-application/web-application-2025-group-19/blob/main/Database%20dump.docx)

## UI prototype (Figma)
- Figma prototype main UI: https://www.figma.com/make/wONpMO5WGtPqdMSlWbuxA9/Recreate-Website-Design?t=qzE7xTEhYC9LVvCJ-1
- Figma prototype Login: https://www.figma.com/make/JrogweV06uG5t0fhWOjKEk/Recreate-Login-Window?t=vCxRCXjFN6Bna2wM-1

## Drive
- https://ugentbe-my.sharepoint.com/:f:/g/personal/arnaud_jaecques_ugent_be/IgCd0dt7Q8wiRoBLI81ikfTsAdTRqt0Y5nGa8vY2vXmKJEU?e=EuSlh9

## User stories
- https://ugentbe-my.sharepoint.com/:w:/g/personal/arnaud_jaecques_ugent_be/IQDbdpV4vQuvTrWji7QD3_REAXQZVZH6l7c5gLp39xalDbY?e=momsw7

## Powerpoint en demo
- Powerpoint: https://ugentbe-my.sharepoint.com/:p:/g/personal/arnaud_jaecques_ugent_be/IQDIiRxAlfiqRZdW1om_jEzoAZs-xQSxQWOQZgW5MJAxBIw?e=Pv0BnI
- Demo: https://ugentbe-my.sharepoint.com/:v:/g/personal/arnaud_jaecques_ugent_be/IQBOhCrtPRPkQ6n5SEKFMr2LAa11SJEweDdP1Xy4FDOORCk?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJPbmVEcml2ZUZvckJ1c2luZXNzIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXciLCJyZWZlcnJhbFZpZXciOiJNeUZpbGVzTGlua0NvcHkifX0&e=FAyG12

## Feedback sessions
- Session 1: https://ugentbe-my.sharepoint.com/:u:/g/personal/arnaud_jaecques_ugent_be/IQA_-_l5SDhCS5eAF85HnGX7AeuyUmlbahbkWZy8kQ06WMk?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJPbmVEcml2ZUZvckJ1c2luZXNzIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXciLCJyZWZlcnJhbFZpZXciOiJNeUZpbGVzTGlua0NvcHkifX0&e=qjdr0W
- Session 2: https://ugentbe-my.sharepoint.com/:u:/g/personal/arnaud_jaecques_ugent_be/IQAJ0pk106mzRLbj72N3vQzmAcWHpwKqf0QBq6uOm0Y6A80?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJPbmVEcml2ZUZvckJ1c2luZXNzIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXciLCJyZWZlcnJhbFZpZXciOiJNeUZpbGVzTGlua0NvcHkifX0&e=WBIIdP

## MVP Handover & IP Assignment Agreement
- https://ugentbe-my.sharepoint.com/:b:/g/personal/arnaud_jaecques_ugent_be/IQDNY2XYFONBSLC7-spZcwaqActUruyT3IduEm9aLng6syM?e=Aezb3s

## Team
- Alexia Lehouck
- Pierre Broekaert
- Herben Vanderhaegen
- Michael Vandekerckhove
- Arnaud Jaecques
