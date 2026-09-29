"""Single-call routing via the free public OSRM demo server (no API key)."""
import numpy as np
import requests
from django.conf import settings

from .geo import decode_polyline


class RoutingError(RuntimeError):
    pass


def fetch_route(start, finish):
    """One HTTP request. Returns dict(points=(n,2) lat/lon array, distance_mi, duration_min)."""
    cfg = settings.FUEL
    url = (f"{cfg['OSRM_URL']}/route/v1/driving/{start[1]:.6f},{start[0]:.6f};{finish[1]:.6f},{finish[0]:.6f}")
    try:
        resp = requests.get(
            url, params={"overview": "full", "geometries": "polyline6", "steps": "false", "alternatives": "false"},
            headers={"User-Agent": cfg["USER_AGENT"]}, timeout=cfg["HTTP_TIMEOUT"],
        )
        resp.raise_for_status()
        body = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise ConnectionError(f"routing service unavailable: {exc}") from exc
    if body.get("code") != "Ok" or not body.get("routes"):
        raise RoutingError(body.get("message") or f"no drivable route found ({body.get('code')})")
    r = body["routes"][0]
    return {
        "points": np.asarray(decode_polyline(r["geometry"], 6)),
        "distance_mi": r["distance"] / 1609.344,
        "duration_min": r["duration"] / 60.0,
    }
