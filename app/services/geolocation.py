import math
from datetime import date, timedelta
from typing import List, Tuple, Dict

import requests
from flask import current_app

from ..models import db, Region, Delivery, RegionAddress

MAX_DELIVERIES_PER_DAY = 13
DEFAULT_SAME_DAY_RADIUS_KM = 15.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Bereken afstand in km tussen twee coördinaten met de haversine-formule."""
    r = 6371.0  # aardstraal in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(
        d_lambda / 2
    ) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def geocode_address_with_mapbox(address: str) -> Tuple[float, float]:
    """
    Geocode een adres via Mapbox en retourneer (lat, lng).
    Verwacht dat MAPBOX_ACCESS_TOKEN in de Flask-config staat.
    """
    token = current_app.config.get("MAPBOX_ACCESS_TOKEN")
    if not token:
        raise ValueError("MAPBOX_ACCESS_TOKEN is niet geconfigureerd.")

    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{address}.json"
    params = {"access_token": token, "limit": 1}
    resp = requests.get(url, params=params, timeout=5)
    resp.raise_for_status()
    data = resp.json()

    features = data.get("features") or []
    if not features:
        raise ValueError("Adres niet gevonden.")

    center = features[0].get("center") or []
    if len(center) != 2:
        raise ValueError("Onverwachte geocodeer-respons.")

    lng, lat = center
    return float(lat), float(lng)


def detect_region_for_coordinates(lat: float, lng: float, tenant_id: int = None) -> Region:
    """
    Zoek de beste Region voor gegeven coördinaten.
    Gooit ValueError indien geen regio binnen zijn straal valt.
    
    Note: Deze functie vereist tenant_id voor multi-tenant support.
    """
    query = Region.query
    if tenant_id:
        query = query.filter_by(tenant_id=tenant_id)
    
    regions: List[Region] = query.all()
    best_region = None
    best_distance = float("inf")

    for region in regions:
        if region.center_lat and region.center_lng:
            distance = haversine_km(lat, lng, region.center_lat, region.center_lng)
            radius = region.radius_km or 30.0
            if distance <= radius and distance < best_distance:
                best_region = region
                best_distance = distance

    if best_region is None:
        raise ValueError("Adres ligt buiten de leveringsregio's.")

    return best_region


def get_suggested_dates_for_new_delivery(
    address: str, same_day_radius_km: float, tenant_id: int = None
) -> Tuple[Region, float, float, List[Dict]]:
    """
    Simpele implementatie:
    - Geocode adres
    - Bepaal regio
    - Voor de komende 14 dagen: tel leveringen in deze regio
      * total = alle leveringen op die datum in de regio
      * nearby = leveringen op die datum binnen same_day_radius_km van het adres
    
    Note: Deze functie gebruikt RegionAddress om leveringen per datum te vinden.
    """
    lat, lng = geocode_address_with_mapbox(address)
    region = detect_region_for_coordinates(lat, lng, tenant_id)

    today = date.today()
    horizon = today + timedelta(days=14)

    suggestions: List[Dict] = []
    current = today
    while current <= horizon:
        # Gebruik RegionAddress om leveringen per datum te vinden
        query = RegionAddress.query.filter(
            RegionAddress.scheduled_date == current,
            RegionAddress.region_id == region.region_id,
        )
        if tenant_id:
            query = query.filter_by(tenant_id=tenant_id)
        
        day_addresses: List[RegionAddress] = query.all()

        total = len(day_addresses)
        nearby = 0
        for addr in day_addresses:
            dist = haversine_km(lat, lng, addr.latitude, addr.longitude)
            if dist <= same_day_radius_km:
                nearby += 1

        suggestions.append(
            {
                "date": current,
                "nearby": nearby,
                "total": total,
            }
        )
        current += timedelta(days=1)

    return region, lat, lng, suggestions














