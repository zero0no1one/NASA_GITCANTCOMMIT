"""Where the Sun and Earth are overhead on the Moon at any time from 2026 to 2030, from NASA JPL Horizons.

The hourly table (data/ephemeris_moon_2026_2030.csv.gz, built by data/make_ephemeris.py) holds the sub-Earth and
sub-solar points in the Moon's mean-Earth/polar-axis frame (east longitude positive) and the Earth-Moon distance.
Values between hours are interpolated linearly, with longitudes unwrapped first so they don't jump at 360°.
"""
import csv
import gzip
from functools import lru_cache
from pathlib import Path
import numpy as np

TABLE = Path(__file__).resolve().parents[1]/'data'/'ephemeris_moon_2026_2030.csv.gz'
EPOCH = np.datetime64('2026-01-01T00:00', 's')


@lru_cache(maxsize=1)
def _table():
    with gzip.open(TABLE, 'rt', newline='') as f:
        rows = list(csv.reader(f))[1:]
    hours = np.array([(np.datetime64(r[0][:-1], 's')-EPOCH)/np.timedelta64(1, 'h') for r in rows])
    values = np.array([[float(v) for v in r[1:]] for r in rows])
    earth_lon, earth_lat, sun_lon, sun_lat, distance = values.T
    return {'hours': hours, 'earth_lon': np.unwrap(earth_lon, period=360.), 'earth_lat': earth_lat,
            'sun_lon': np.unwrap(sun_lon, period=360.), 'sun_lat': sun_lat, 'earth_distance_km': distance}


def span():
    """First and last time the table covers, as UTC datetimes."""
    hours = _table()['hours']
    return EPOCH+np.timedelta64(int(hours[0]), 'h'), EPOCH+np.timedelta64(int(hours[-1]), 'h')


def hours_since_epoch(times):
    return (np.asarray(times, 'datetime64[s]')-EPOCH)/np.timedelta64(1, 'h')


def at(times):
    """Sub-solar and sub-Earth points (degrees, east longitude in 0-360) and Earth's distance (km) at the given UTC times."""
    t = _table()
    h = hours_since_epoch(times)
    if np.any(h < t['hours'][0]) or np.any(h > t['hours'][-1]):
        first, last = span()
        raise ValueError(f'Dates must be between {first} and {last} UTC.')
    out = {key: np.interp(h, t['hours'], t[key]) for key in ('earth_lon', 'earth_lat', 'sun_lon', 'sun_lat', 'earth_distance_km')}
    out['earth_lon'] %= 360.
    out['sun_lon'] %= 360.
    return out
