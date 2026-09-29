import hashlib
import json
import time
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .services import geocode, osrm, planner
from .services.geo import haversine_mi
from .services.stations import get_stations


def health(request):
    return JsonResponse({"status": "ok", "stations_loaded": len(get_stations())})


def _params(request):
    if request.method == "POST" and request.body:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            raise ValueError("body must be valid JSON")
    else:
        data = request.GET
    return data.get("start"), data.get("finish"), data.get("format", "json")


def _error(message, status):
    return JsonResponse({"error": message}, status=status)


@require_http_methods(["GET", "POST"])
def plan_route(request):
    t0 = time.perf_counter()
    cfg = settings.FUEL
    try:
        start_txt, finish_txt, fmt = _params(request)
    except ValueError as exc:
        return _error(str(exc), 400)
    if not start_txt or not finish_txt:
        return _error("Provide 'start' and 'finish' (e.g. 'Los Angeles, CA', a street address, or 'lat,lon').", 400)

    api_calls = 0
    try:
        s_lat, s_lon, s_label, n1 = geocode.resolve(start_txt)
        f_lat, f_lon, f_label, n2 = geocode.resolve(finish_txt)
        api_calls += n1 + n2

        key = "route:" + hashlib.sha1(f"{s_lat:.4f},{s_lon:.4f}|{f_lat:.4f},{f_lon:.4f}".encode()).hexdigest()
        route = cache.get(key)
        cached = route is not None
        if not cached:
            route = osrm.fetch_route((s_lat, s_lon), (f_lat, f_lon))
            api_calls += 1
            cache.set(key, route, cfg["CACHE_SECONDS"])

        index = get_stations()
        points, total = route["points"], route["distance_mi"]
        miles = planner.route_mileposts(points, total)
        cands = planner.stations_along_route(points, miles, index, cfg["CORRIDOR_MILES"])
        stops = planner.plan_fuel(cands, index.price, total, cfg["MAX_RANGE_MILES"], cfg["MPG"], cfg["MAX_RANGE_MILES"])
    except geocode.GeocodeError as exc:
        return _error(str(exc), 400)
    except planner.InfeasibleRoute as exc:
        return _error(f"Trip cannot be completed with a {cfg['MAX_RANGE_MILES']:.0f}-mile range: {exc}", 422)
    except osrm.RoutingError as exc:
        return _error(str(exc), 422)
    except ConnectionError as exc:
        return _error(str(exc), 502)

    fuel_stops = []
    for s in stops:
        mile, idx, off = s["cand"]
        st = index.rows[idx]
        fuel_stops.append({
            "station_id": st["id"], "name": st["name"], "address": st["address"],
            "city": st["city"], "state": st["state"],
            "location": {"lat": st["lat"], "lon": st["lon"], "accuracy": "city centroid"},
            "route_mile": round(mile, 1), "miles_off_route": round(off, 1),
            "price_per_gallon": round(st["price"], 3),
            "gallons": round(s["gallons"], 2), "cost": round(s["cost"], 2),
        })

    step = max(1, len(points) // 3000)
    thin = points[::step].tolist()
    if thin[-1] != points[-1].tolist():
        thin.append(points[-1].tolist())

    result = {
        "start": {"input": start_txt, "resolved": s_label, "lat": s_lat, "lon": s_lon},
        "finish": {"input": finish_txt, "resolved": f_label, "lat": f_lat, "lon": f_lon},
        "distance_miles": round(total, 1),
        "duration_hours": round(route["duration_min"] / 60, 2),
        "total_fuel_cost": round(sum(s["cost"] for s in stops), 2),
        "total_gallons_purchased": round(sum(s["gallons"] for s in stops), 2),
        "fuel_stops": fuel_stops,
        "route": {"type": "Feature", "properties": {},
                  "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in thin]}},
        "assumptions": {
            "max_range_miles": cfg["MAX_RANGE_MILES"], "mpg": cfg["MPG"],
            "starts_with_full_tank": True,
            "cost_counts": "only fuel purchased at the listed stops (initial tank is not billed)",
            "station_corridor_miles": cfg["CORRIDOR_MILES"],
            "station_locations": "city centroids (source CSV has no coordinates)",
        },
        "meta": {"external_api_calls": api_calls, "route_cached": cached,
                 "stations_considered": len(cands), "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1)},
    }
    if fmt == "html":
        return render(request, "routing/map.html", {"data": result})
    result["map_url"] = request.build_absolute_uri(request.path) + "?" + urlencode(
        {"start": start_txt, "finish": finish_txt, "format": "html"})
    return JsonResponse(result)
