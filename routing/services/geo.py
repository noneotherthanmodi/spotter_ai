"""Small geometry helpers (numpy only)."""
import numpy as np

EARTH_RADIUS_MI = 3958.7613


def to_xyz(lat, lon):
    """Unit-sphere 3D vectors scaled to miles. Chord distance ~ arc distance for short hops,
    which lets a KD-tree do accurate 'nearest route point' lookups anywhere on the globe."""
    lat, lon = np.radians(np.asarray(lat, float)), np.radians(np.asarray(lon, float))
    c = np.cos(lat)
    return EARTH_RADIUS_MI * np.column_stack((c * np.cos(lon), c * np.sin(lon), np.sin(lat)))


def haversine_mi(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * np.arcsin(np.sqrt(a))


def decode_polyline(encoded, precision=6):
    """Decode a Google/OSRM encoded polyline into an (n, 2) array of [lat, lon]."""
    coords, index, lat, lon, factor = [], 0, 0, 0, 10 ** precision
    while index < len(encoded):
        for is_lat in (True, False):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if is_lat:
                lat += delta
            else:
                lon += delta
        coords.append((lat / factor, lon / factor))
    return np.array(coords)


def encode_polyline(points, precision=6):
    """Inverse of decode_polyline (used by tests / the mock router)."""
    factor, out, prev_lat, prev_lon = 10 ** precision, [], 0, 0
    for lat, lon in points:
        ilat, ilon = round(lat * factor), round(lon * factor)
        for d in (ilat - prev_lat, ilon - prev_lon):
            d = ~(d << 1) if d < 0 else d << 1
            while d >= 0x20:
                out.append(chr((0x20 | (d & 0x1F)) + 63))
                d >>= 5
            out.append(chr(d + 63))
        prev_lat, prev_lon = ilat, ilon
    return "".join(out)
