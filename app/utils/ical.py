# app/utils/ical.py
"""
iCal (.ics) utility voor het exporteren van leveringen naar kalenderapps.
Compatibel met iPhone/Apple Calendar, Google Calendar, Outlook, etc.
"""

from datetime import datetime, timedelta
from icalendar import Calendar, Event
import hashlib


def create_delivery_ical(deliveries: list, calendar_name: str = "Leveringen") -> bytes:
    """
    Maak een iCal bestand van een lijst leveringen.
    
    Args:
        deliveries: Lijst van dictionaries met delivery info:
            - delivery_id: unieke ID
            - scheduled_date: datum (date object)
            - address: leveradres (optioneel)
            - region_name: regio naam
            - order_id: order nummer (optioneel)
            - product_id: product ID (optioneel)
            - status: delivery status
        calendar_name: Naam van de kalender
    
    Returns:
        bytes: iCal bestand content
    """
    cal = Calendar()
    
    # Kalender metadata
    cal.add('prodid', '-//Sleep Inn Scheduler//sleepinn.be//')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    cal.add('x-wr-calname', f"Sleep Inn - {calendar_name}")
    cal.add('x-wr-timezone', 'Europe/Brussels')
    
    for delivery in deliveries:
        try:
            event = Event()
            
            # Unieke ID voor het event
            delivery_id = delivery.get('delivery_id', 'unknown')
            uid = f"delivery-{delivery_id}@sleepinn.be"
            event.add('uid', uid)
            
            # Titel van het event
            region = delivery.get('region_name', 'Onbekend') or 'Onbekend'
            product_description = delivery.get('product_description', '') or ''
            product_id = delivery.get('product_id', delivery.get('order_id', '')) or ''
            
            # Gebruik product_description als die beschikbaar is, anders product_id
            if product_description:
                title = f"📦 {product_description}"
            elif product_id:
                title = f"📦 Levering #{product_id}"
            else:
                title = f"📦 Levering"
            
            if region and region != 'Onbekend':
                title += f" - {region}"
            
            # Zorg dat title een string is (geen None)
            event.add('summary', str(title) if title else 'Levering')
            
            # Datum (hele dag event)
            scheduled_date = delivery.get('scheduled_date')
            if scheduled_date:
                try:
                    if isinstance(scheduled_date, datetime):
                        scheduled_date = scheduled_date.date()
                    elif isinstance(scheduled_date, str):
                        # Probeer string te parsen
                        from datetime import datetime as dt
                        scheduled_date = dt.strptime(scheduled_date, '%Y-%m-%d').date()
                    
                    # Voor hele dag events: gebruik date object (icalendar converteert automatisch)
                    if scheduled_date:
                        event.add('dtstart', scheduled_date)
                        event.add('dtend', scheduled_date + timedelta(days=1))
                except Exception as date_error:
                    # Skip deze delivery als datum niet geldig is
                    continue
            
            # Locatie
            address = delivery.get('address', '') or ''
            if address:
                event.add('location', str(address))
            elif region and region != 'Onbekend':
                event.add('location', f"Regio: {region}")
            
            # Beschrijving
            description_parts = []
            if product_description:
                description_parts.append(f"Product: {product_description}")
            elif product_id:
                description_parts.append(f"Product ID: #{product_id}")
            order_id = delivery.get('order_id')
            if order_id:
                description_parts.append(f"Order ID: #{order_id}")
            if region and region != 'Onbekend':
                description_parts.append(f"Regio: {region}")
            status = delivery.get('status')
            if status:
                status_str = str(status).replace('DeliveryStatus.', '').replace('DeliveryStatus', '')
                if status_str:
                    description_parts.append(f"Status: {status_str}")
            if address:
                description_parts.append(f"Adres: {address}")
            
            # Beschrijving (zorg dat het een string is)
            description_text = '\n'.join(description_parts) if description_parts else 'Levering'
            event.add('description', str(description_text))
            
            # Status
            event.add('status', 'CONFIRMED')
            
            # Timestamp (vereist voor iCal)
            try:
                event.add('dtstamp', datetime.utcnow())
            except Exception:
                # Fallback naar huidige tijd
                from datetime import datetime as dt
                event.add('dtstamp', dt.now())
            
            # Categorie (optioneel, sommige clients ondersteunen dit niet)
            try:
                event.add('categories', ['Levering'])
            except Exception:
                pass
            
            cal.add_component(event)
        except Exception as delivery_error:
            # Skip deze delivery als er een fout optreedt, maar log het
            import logging
            logging.warning(f"Skipping delivery due to error: {delivery_error}")
            continue
    
    # Genereer iCal content als bytes
    try:
        ical_bytes = cal.to_ical()
        # Zorg dat het correct geformatteerd is voor Google Calendar
        if isinstance(ical_bytes, bytes):
            return ical_bytes
        else:
            return ical_bytes.encode('utf-8')
    except Exception as e:
        # Fallback: maak een minimale geldige iCal
        cal_minimal = Calendar()
        cal_minimal.add('prodid', '-//Sleep Inn Scheduler//sleepinn.be//')
        cal_minimal.add('version', '2.0')
        cal_minimal.add('calscale', 'GREGORIAN')
        cal_minimal.add('method', 'PUBLISH')
        cal_minimal.add('x-wr-calname', f"Sleep Inn - {calendar_name}")
        ical_bytes = cal_minimal.to_ical()
        if isinstance(ical_bytes, bytes):
            return ical_bytes
        else:
            return ical_bytes.encode('utf-8')


def create_driver_schedule_ical(driver_name: str, deliveries: list, 
                                 availability_dates: list = None) -> bytes:
    """
    Maak een iCal bestand voor een specifieke chauffeur met zijn leveringen
    en beschikbaarheidsdagen.
    
    Args:
        driver_name: Naam van de chauffeur
        deliveries: Lijst van leveringen (zie create_delivery_ical)
        availability_dates: Lijst van datums waarop chauffeur beschikbaar is
    
    Returns:
        bytes: iCal bestand content
    """
    cal = Calendar()
    
    # Kalender metadata
    cal.add('prodid', '-//Sleep Inn Scheduler//sleepinn.be//')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    cal.add('x-wr-calname', f"Sleep Inn - Leveringen {driver_name}")
    cal.add('x-wr-timezone', 'Europe/Brussels')
    
    # Voeg leveringen toe
    for delivery in deliveries:
        event = Event()
        
        uid = f"delivery-{delivery.get('delivery_id', 'unknown')}-{driver_name.replace(' ', '')}@sleepinn.be"
        event.add('uid', uid)
        
        region = delivery.get('region_name', 'Onbekend')
        product_id = delivery.get('product_id', delivery.get('order_id', ''))
        title = f"🚚 Levering #{product_id}" if product_id else f"🚚 Levering"
        if region:
            title += f" - {region}"
        event.add('summary', title)
        
        scheduled_date = delivery.get('scheduled_date')
        if scheduled_date:
            if isinstance(scheduled_date, datetime):
                scheduled_date = scheduled_date.date()
            # Voor chauffeurs: tijdslot van 8:00 - 18:00
            start_time = datetime.combine(scheduled_date, datetime.min.time().replace(hour=8))
            end_time = datetime.combine(scheduled_date, datetime.min.time().replace(hour=18))
            event.add('dtstart', start_time)
            event.add('dtend', end_time)
        
        address = delivery.get('address', '')
        if address:
            event.add('location', address)
        elif region:
            event.add('location', f"Regio: {region}")
        
        description_parts = [f"Chauffeur: {driver_name}"]
        if product_id:
            description_parts.append(f"Product ID: #{product_id}")
        if region:
            description_parts.append(f"Regio: {region}")
        if address:
            description_parts.append(f"Adres: {address}")
        
        event.add('description', '\n'.join(description_parts))
        event.add('status', 'CONFIRMED')
        event.add('dtstamp', datetime.utcnow())
        event.add('categories', ['Werk', 'Levering'])
        
        cal.add_component(event)
    
    # Voeg beschikbaarheidsdagen toe (als reminder)
    if availability_dates:
        for avail_date in availability_dates:
            event = Event()
            
            uid_hash = hashlib.md5(f"{driver_name}-{avail_date}".encode()).hexdigest()[:8]
            event.add('uid', f"availability-{uid_hash}@sleepinn.be")
            event.add('summary', f"✅ Beschikbaar voor leveringen")
            
            if isinstance(avail_date, datetime):
                avail_date = avail_date.date()
            event.add('dtstart', avail_date)
            event.add('dtend', avail_date + timedelta(days=1))
            
            event.add('description', f"Je bent beschikbaar ingepland voor leveringen op deze dag.")
            event.add('status', 'CONFIRMED')
            event.add('dtstamp', datetime.utcnow())
            event.add('categories', ['Beschikbaarheid'])
            event.add('transp', 'TRANSPARENT')  # Niet als "bezet" tonen
            
            cal.add_component(event)
    
    # Genereer iCal content als bytes
    ical_bytes = cal.to_ical()
    if isinstance(ical_bytes, bytes):
        return ical_bytes
    else:
        return ical_bytes.encode('utf-8')


def create_single_delivery_ical(delivery: dict) -> bytes:
    """
    Maak een iCal bestand voor een enkele levering.
    Handig voor het snel toevoegen aan agenda vanuit detail view.
    """
    return create_delivery_ical([delivery], "Levering")

