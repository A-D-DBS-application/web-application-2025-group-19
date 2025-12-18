[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/DxqGQVx4)
# Web Application 2025 — Functies

Korte beschrijving van wat je op de site kunt doen.

## Hoofdschermen
- Home (`/`): dashboard met navigatie naar bestellingen, runs, chauffeurs en trucks.
- Inloggen/Registreren (`/login`, `/register`): accounts aanmaken en inloggen.
- Listings (`/listings`): producten bekijken en demo-bestellingen starten.
- Nieuwe listing (`/add-listing`): handmatig een product/levering toevoegen.
- Trucks (`/trucks`): voertuigen bekijken en beheren.
- Drivers (`/drivers`): chauffeurs bekijken, toevoegen, beschikbaarheid beheren.

## Bestellingen en leveringen
- Orders aanmaken vanuit listings of het formulier op `/add-listing`.
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
