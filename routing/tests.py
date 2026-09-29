import random
from unittest import mock

import numpy as np
from django.core.cache import cache
from django.test import SimpleTestCase

from .services import planner
from .services.geo import decode_polyline, encode_polyline, haversine_mi


def brute_force_min_cost(cands, prices, total, R, mpg, start_range):
    """Exact DP over (station, fuel level in 1-mile units) for cross-checking the greedy planner."""
    miles = [c[0] for c in cands] + [total]
    p = [prices[c[1]] for c in cands] + [0.0]
    U = 1  # discretize fuel to whole miles (test instances use integer miles)
    INF = float("inf")
    best = {(0, start_range): 0.0}
    prev_m = 0
    for i, m in enumerate(miles):
        nxt = {}
        for (j, f), c in best.items():
            pass
        break
    # simple forward DP
    cost = [[INF] * (R + 1) for _ in range(len(miles))]
    prev = 0
    fuel0 = start_range - int(miles[0])
    if fuel0 < 0:
        return INF
    cost[0][fuel0] = 0.0
    for i in range(len(miles)):
        # buy at station i (not at the destination)
        if i < len(miles) - 1:
            for f in range(R + 1):
                if cost[i][f] == INF:
                    continue
                for g in range(f + 1, R + 1):
                    c2 = cost[i][f] + (g - f) / mpg * p[i]
                    if c2 < cost[i][g]:
                        cost[i][g] = c2
            d = int(miles[i + 1] - miles[i])
            for f in range(d, R + 1):
                if cost[i][f] < cost[i + 1][f - d]:
                    cost[i + 1][f - d] = cost[i][f]
    return min(cost[-1])


class PlannerOptimality(SimpleTestCase):
    def test_matches_exact_dp_on_random_instances(self):
        rnd = random.Random(7)
        for _ in range(300):
            R, mpg = 50, 10.0
            total = rnd.randint(60, 300)
            n = rnd.randint(4, 14)
            miles = sorted(rnd.sample(range(1, total), n))
            prices = [round(rnd.uniform(2.5, 4.5), 3) for _ in range(n)]
            cands = [(float(m), i, 0.0) for i, m in enumerate(miles)]
            try:
                stops = planner.plan_fuel(cands, prices, float(total), R, mpg, R)
            except planner.InfeasibleRoute:
                self.assertEqual(brute_force_min_cost(cands, prices, total, R, mpg, R), float("inf"))
                continue
            got = sum(s["cost"] for s in stops)
            self.assertAlmostEqual(got, brute_force_min_cost(cands, prices, total, R, mpg, R), places=6)

    def test_never_runs_dry(self):
        rnd = random.Random(3)
        for _ in range(200):
            R, total = 500, rnd.randint(600, 3000)
            miles = sorted(rnd.sample(range(1, total), 40))
            prices = [rnd.uniform(2.8, 4.2) for _ in miles]
            cands = [(float(m), i, 0.0) for i, m in enumerate(miles)]
            try:
                stops = planner.plan_fuel(cands, prices, float(total), R, 10.0, R)
            except planner.InfeasibleRoute:
                continue
            fuel, pos = R, 0.0
            buys = {s["cand"][0]: s["gallons"] * 10 for s in stops}
            for m in miles + [float(total)]:
                fuel -= m - pos
                pos = m
                self.assertGreaterEqual(fuel, -1e-6)
                fuel = min(R + 1e-6, fuel + buys.get(m, 0))
                self.assertLessEqual(fuel, R + 1e-6)

    def test_short_trip_needs_no_stops(self):
        self.assertEqual(planner.plan_fuel([(100.0, 0, 0.0)], [3.0], 300.0, 500, 10.0, 500), [])

    def test_gap_too_large_is_infeasible(self):
        with self.assertRaises(planner.InfeasibleRoute):
            planner.plan_fuel([(100.0, 0, 0.0)], [3.0], 1200.0, 500, 10.0, 500)


class GeoTests(SimpleTestCase):
    def test_polyline_roundtrip(self):
        pts = [(34.05, -118.24), (35.1, -110.7), (40.7128, -74.006)]
        np.testing.assert_allclose(decode_polyline(encode_polyline(pts)), pts, atol=1e-6)


def fake_route(start, finish, wps=None):
    """Densified path through waypoints, ~1 point per mile, distance = 1.15x geodesic."""
    wps = wps or [start, finish]
    pts = []
    for a, b in zip(wps[:-1], wps[1:]):
        n = max(2, int(haversine_mi(a[0], a[1], b[0], b[1])))
        pts += list(zip(np.linspace(a[0], b[0], n), np.linspace(a[1], b[1], n)))
    pts = np.array(pts)
    seg = haversine_mi(pts[:-1, 0], pts[:-1, 1], pts[1:, 0], pts[1:, 1]).sum()
    return {"points": pts, "distance_mi": seg * 1.12, "duration_min": seg * 1.12 / 62 * 60}


class ApiTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def call(self, start, finish, **kw):
        wps = kw.pop("wps", None)
        with mock.patch("routing.services.osrm.fetch_route", side_effect=lambda s, f: fake_route(s, f, wps)) as m:
            resp = self.client.get("/api/route/", {"start": start, "finish": finish, **kw})
        return resp, m

    def test_cross_country(self):
        wps = [(34.05, -118.24), (35.2, -111.65), (35.08, -106.65), (35.47, -97.52), (38.63, -90.2),
               (39.77, -86.16), (39.96, -83.0), (40.44, -80.0), (40.71, -74.0)]
        resp, m = self.call("Los Angeles, CA", "New York, NY", wps=wps)
        self.assertEqual(resp.status_code, 200)
        d = resp.json()
        self.assertEqual(m.call_count, 1)
        self.assertEqual(d["meta"]["external_api_calls"], 1)
        self.assertGreaterEqual(len(d["fuel_stops"]), 4)
        self.assertAlmostEqual(d["total_fuel_cost"], sum(s["cost"] for s in d["fuel_stops"]), places=1)
        prev = 0
        for s in d["fuel_stops"]:
            self.assertGreater(s["route_mile"], prev)
            self.assertLessEqual(s["route_mile"] - prev, 500.01)
            prev = s["route_mile"]
        print("\nLA->NYC:", d["distance_miles"], "mi | stops:", len(d["fuel_stops"]), "| $", d["total_fuel_cost"],
              "| ms:", d["meta"]["elapsed_ms"], "| stations near route:", d["meta"]["stations_considered"])
        for s in d["fuel_stops"]:
            print("  mile %7.1f  %-28s %-14s $%.3f  %6.2f gal  $%.2f" % (
                s["route_mile"], s["name"][:28], s["city"] + "," + s["state"], s["price_per_gallon"], s["gallons"], s["cost"]))

    def test_second_identical_request_is_cached(self):
        self.call("Chicago, IL", "Dallas, TX")
        resp, m = self.call("Chicago, IL", "Dallas, TX")
        self.assertEqual(m.call_count, 0)
        self.assertTrue(resp.json()["meta"]["route_cached"])
        self.assertEqual(resp.json()["meta"]["external_api_calls"], 0)

    def test_coordinates_input_and_html(self):
        resp, _ = self.call("41.88,-87.63", "32.78,-96.80", format="html")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "leaflet")

    def test_validation(self):
        self.assertEqual(self.client.get("/api/route/").status_code, 400)
        self.assertEqual(self.client.get("/api/route/", {"start": "51.5,-0.12", "finish": "Dallas, TX"}).status_code, 400)

    def test_upstream_failure_is_502(self):
        with mock.patch("routing.services.osrm.fetch_route", side_effect=ConnectionError("down")):
            resp = self.client.get("/api/route/", {"start": "Chicago, IL", "finish": "Dallas, TX"})
        self.assertEqual(resp.status_code, 502)
