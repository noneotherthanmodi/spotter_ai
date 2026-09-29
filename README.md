# Fuel Route API (Django 6.1)

`GET /api/route/?start=Los Angeles, CA&finish=New York, NY` returns the driving route, the cheapest
fuel stops for a 500-mile-range / 10 MPG vehicle, and the total fuel cost.
Add `&format=html` for a Leaflet map page (route + stop markers). `POST` with a JSON body
`{"start": "...", "finish": "..."}` also works. `start`/`finish` accept `"City, ST"`, `"lat,lon"`, or a street address.

## Run
    1. pip install -r requirements.txt
    2. python manage.py test           # planner optimality + API tests (router is mocked)
    3. python manage.py build_stations  # regenerates routing/data/stations.csv from the raw CSV (already built)
    4. python manage.py runserver

**Endpoint: GET /api/route/?start=Los Angeles, CA&finish=New York, NY**

# How it stays fast / within the API budget
**Routing: exactly one call** to the free public OSRM server (`router.project-osrm.org`, no key), `overview=full`.
**Geocoding: zero calls for `"City, ST"` and `"lat,lon"`** (offline city table). Only free-text street addresses
  use Nominatim (1 call each), so the worst case is 3 calls total.
* Repeat trips are served from cache with **0 external calls**.
* The CSV has no coordinates, so `build_stations` geocodes it once, offline, to city centroids, drops Canadian rows,
  and keeps the cheapest price per station ID (6,614 stations). The index lives in memory (loaded on first use).
* Per request: KD-tree over the route polyline, one vectorised nearest-vertex query for all stations in the bbox,
  then an O(n) greedy planner. Server time is a few ms plus the OSRM round-trip.

## Optimisation
Classic gas-station problem: at each station buy just enough to reach the next *cheaper* station within 500 miles,
otherwise fill the tank. This greedy is optimal; the test suite checks it against an exact DP on 300 random instances.

## Assumptions (also echoed in every response under `assumptions`)
* Vehicle **starts with a full 500-mile tank**; `total_fuel_cost` counts fuel bought at the listed stops only.
* Stations count if their city centroid is within **10 miles** of the route (`CORRIDOR_MILES`); detour cost is ignored.
* Station coordinates are city centroids, so map pins are approximate (typically a few miles).
* Fuel stops with tiny purchases can appear when that is genuinely cheapest.

## Response shape
`distance_miles, duration_hours, total_fuel_cost, total_gallons_purchased, fuel_stops[], route (GeoJSON), assumptions, meta`
(`meta` reports `external_api_calls`, `route_cached`, `elapsed_ms`).
