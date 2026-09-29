"""In-memory station index, loaded once per process from data/stations.csv."""
import csv
from functools import lru_cache
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class StationIndex:
    def __init__(self, rows):
        self.rows = rows
        self.lat = np.array([r["lat"] for r in rows])
        self.lon = np.array([r["lon"] for r in rows])
        self.price = np.array([r["price"] for r in rows])

    def __len__(self):
        return len(self.rows)


@lru_cache(maxsize=1)
def get_stations() -> StationIndex:
    rows = []
    with open(DATA_DIR / "stations.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "id": int(r["id"]), "name": r["name"], "address": r["address"],
                "city": r["city"], "state": r["state"],
                "lat": float(r["lat"]), "lon": float(r["lon"]), "price": float(r["price"]),
            })
    return StationIndex(rows)


@lru_cache(maxsize=1)
def get_cities():
    """(city|state) -> (lat, lon); used to resolve 'City, ST' inputs without any API call."""
    from .stations_build import city_key
    out = {}
    with open(DATA_DIR / "us_cities.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            out.setdefault(city_key(r["CITY"], r["STATE_CODE"]), (float(r["LATITUDE"]), float(r["LONGITUDE"])))
    return out
