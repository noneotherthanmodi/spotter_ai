"""Resolve a start/finish input to (lat, lon, label). Prefers zero-cost offline paths."""
import re

import requests
from django.conf import settings

from .stations import get_cities
from .stations_build import city_key

COORD_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*[,;]\s*(-?\d+(?:\.\d+)?)\s*$")
CITY_RE = re.compile(r"^\s*([^,]+?)\s*,\s*([A-Za-z]{2})\s*(?:,?\s*(?:USA?|United States))?\s*$", re.I)
US_BOX = (24.0, 50.0, -125.5, -66.0)  # rough contiguous-US bounds (min_lat, max_lat, min_lon, max_lon)


class GeocodeError(ValueError):
    pass


def in_usa(lat, lon):
    # contiguous US, plus a coarse Alaska / Hawaii allowance
    return (US_BOX[0] <= lat <= US_BOX[1] and US_BOX[2] <= lon <= US_BOX[3]) or \
           (51 <= lat <= 72 and -170 <= lon <= -129) or (18 <= lat <= 23 and -161 <= lon <= -154)


def resolve(text):
    """Returns (lat, lon, label, api_calls_used)."""
    text = (text or "").strip()
    if not text:
        raise GeocodeError("empty location")

    m = COORD_RE.match(text)
    if m:
        lat, lon = float(m[1]), float(m[2])
        if not in_usa(lat, lon):
            raise GeocodeError(f"coordinates {lat},{lon} are outside the USA")
        return lat, lon, f"{lat:.5f},{lon:.5f}", 0

    m = CITY_RE.match(text)
    if m:
        hit = get_cities().get(city_key(m[1], m[2].upper()))
        if hit:
            return hit[0], hit[1], f"{m[1].title()}, {m[2].upper()}", 0

    # Fallback for street addresses / unknown places: one Nominatim call.
    cfg = settings.FUEL
    try:
        resp = requests.get(
            f"{cfg['NOMINATIM_URL']}/search",
            params={"q": text, "format": "jsonv2", "limit": 1, "countrycodes": "us"},
            headers={"User-Agent": cfg["USER_AGENT"]}, timeout=cfg["HTTP_TIMEOUT"],
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise ConnectionError(f"geocoder unavailable: {exc}") from exc
    if not data:
        raise GeocodeError(f"could not find a US location for '{text}'")
    return float(data[0]["lat"]), float(data[0]["lon"]), data[0]["display_name"], 1
