"""Match stations to a route and choose the cheapest fuel-purchase plan.

Optimality: this is the classic "gas station problem". With a fixed tank size and per-station
prices, the greedy rule below is optimal: at each station, buy only enough to reach the next
cheaper station in range; if none is in range, fill the tank.
"""
import numpy as np
from scipy.spatial import cKDTree

from .geo import haversine_mi, to_xyz

EPS = 1e-9


class InfeasibleRoute(ValueError):
    pass


def route_mileposts(points, total_miles):
    """Cumulative miles at each route vertex, rescaled so the last vertex == routed distance."""
    seg = haversine_mi(points[:-1, 0], points[:-1, 1], points[1:, 0], points[1:, 1])
    cum = np.concatenate(([0.0], np.cumsum(seg)))
    return cum * (total_miles / cum[-1]) if cum[-1] > 0 else cum


def stations_along_route(points, mileposts, index, corridor_miles):
    """Return [(mile, station_idx, off_route_miles)] sorted by mile, for stations near the route."""
    pad = corridor_miles / 60.0 + 0.05  # degrees, generous
    keep = np.flatnonzero(
        (index.lat >= points[:, 0].min() - pad) & (index.lat <= points[:, 0].max() + pad)
        & (index.lon >= points[:, 1].min() - pad * 1.6) & (index.lon <= points[:, 1].max() + pad * 1.6)
    )
    if keep.size == 0:
        return []
    tree = cKDTree(to_xyz(points[:, 0], points[:, 1]))
    dist, nearest = tree.query(to_xyz(index.lat[keep], index.lon[keep]), distance_upper_bound=corridor_miles)
    ok = np.isfinite(dist)
    out = [(float(mileposts[nearest[k]]), int(keep[k]), float(dist[k])) for k in np.flatnonzero(ok)]
    out.sort(key=lambda t: t[0])
    return out


def plan_fuel(candidates, prices, total_miles, max_range, mpg, start_range):
    """candidates: [(mile, station_idx, off)] sorted by mile. Returns list of purchase dicts."""
    miles = [c[0] for c in candidates]
    p = [prices[c[1]] for c in candidates]
    n = len(candidates)

    # Feasibility: every gap (start -> first, between stations, last -> finish) must be drivable.
    prev, reach = 0.0, start_range
    for m in miles:
        if m - prev > (reach if prev == 0.0 else max_range) + EPS:
            raise InfeasibleRoute(f"no fuel station within range around mile {prev:.0f}")
        prev = m
    if total_miles - prev > (start_range if n == 0 else max_range) + EPS:
        raise InfeasibleRoute(f"no fuel station within range before the destination (mile {prev:.0f})")

    stops, fuel, pos = [], start_range, 0.0  # fuel is tank content expressed in miles of range
    for i in range(n):
        fuel -= miles[i] - pos
        pos = miles[i]
        if total_miles - pos <= fuel + EPS:
            break  # can coast to the finish
        target = None  # distance we must be able to cover: next cheaper stop in range, else full tank
        for j in range(i + 1, n):
            if miles[j] - pos > max_range:
                break
            if p[j] < p[i]:
                target = miles[j] - pos
                break
        if target is None and total_miles - pos <= max_range:
            target = total_miles - pos
        buy_miles = (max_range - fuel) if target is None else max(0.0, target - fuel)
        if buy_miles > EPS:
            gallons = buy_miles / mpg
            fuel += buy_miles
            stops.append({"cand": candidates[i], "gallons": gallons, "cost": gallons * p[i]})
    return stops
