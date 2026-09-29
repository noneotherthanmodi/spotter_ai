"""Offline preprocessing: geocode the CSV (which has no coordinates) to city centroids."""
import csv
import re

from .stations import DATA_DIR

CANADA = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}


def _norm(s):
    s = str(s).lower().replace("saint ", "st ").replace("st.", "st").replace("mt.", "mount")
    return re.sub(r"[^a-z0-9 ]", "", s).strip()


def city_key(city, state):
    return f"{_norm(city)}|{state.strip().upper()}"


def build(raw_path=None, out_path=None):
    raw_path = raw_path or DATA_DIR / "fuel-prices-raw.csv"
    out_path = out_path or DATA_DIR / "stations.csv"
    cities = {}
    with open(DATA_DIR / "us_cities.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            cities.setdefault(city_key(r["CITY"], r["STATE_CODE"]), (r["LATITUDE"], r["LONGITUDE"]))

    best, stats = {}, {"rows": 0, "non_us": 0, "no_geocode": 0}
    with open(raw_path, newline="") as fh:
        for r in csv.DictReader(fh):
            stats["rows"] += 1
            state = r["State"].strip().upper()
            if state in CANADA:
                stats["non_us"] += 1
                continue
            sid, price = int(r["OPIS Truckstop ID"]), float(r["Retail Price"])
            # Same station listed repeatedly (sometimes at different prices): keep the cheapest.
            if sid in best and best[sid]["price"] <= price:
                continue
            geo = cities.get(city_key(r["City"], state))
            if geo is None:
                best.pop(sid, None)
                stats["no_geocode"] += 1
                continue
            best[sid] = {"id": sid, "name": r["Truckstop Name"].strip(), "address": r["Address"].strip(),
                         "city": r["City"].strip(), "state": state, "lat": geo[0], "lon": geo[1], "price": price}

    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "name", "address", "city", "state", "lat", "lon", "price"])
        w.writeheader()
        w.writerows(sorted(best.values(), key=lambda x: x["id"]))
    stats["stations"] = len(best)
    return stats
