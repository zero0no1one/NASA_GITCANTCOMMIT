"""Download where the Sun and Earth are overhead on the Moon, hourly, from NASA JPL's Horizons system.

For each hour it records the sub-Earth point (Horizons quantity 14, ObsSub-LON/LAT, seen from Earth's centre),
the sub-solar point (quantity 15, SunSub-LON/LAT) and the Earth-Moon distance (quantity 20, delta). Longitudes
are east-positive in the Moon's mean-Earth/polar-axis frame (MOON_ME), the frame LOLA maps use. Times are UTC.

Run from "NASA Project":  python data/make_ephemeris.py
Writes data/ephemeris_moon_2026_2030.csv.gz.
"""
import csv
import gzip
import io
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = 'https://ssd.jpl.nasa.gov/api/horizons.api'
AU_KM = 149597870.7
FIRST_YEAR, LAST_YEAR = 2026, 2030
OUT = Path(__file__).resolve().parent/f'ephemeris_moon_{FIRST_YEAR}_{LAST_YEAR}.csv.gz'
MONTHS = {m: i for i, m in enumerate(('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'), 1)}


def fetch_year(year):
    params = {'format': 'text', 'COMMAND': "'301'", 'OBJ_DATA': "'NO'", 'MAKE_EPHEM': "'YES'",
              'EPHEM_TYPE': "'OBSERVER'", 'CENTER': "'500@399'", 'START_TIME': f"'{year}-01-01 00:00'",
              'STOP_TIME': f"'{year+1}-01-01 00:00'", 'STEP_SIZE': "'1 h'", 'QUANTITIES': "'14,15,20'",
              'CSV_FORMAT': "'YES'", 'ANG_FORMAT': "'DEG'", 'EXTRA_PREC': "'YES'"}
    with urllib.request.urlopen(f'{API}?{urllib.parse.urlencode(params)}', timeout=300) as r:
        text = r.read().decode()
    if 'MOON_ME' not in text or '$$SOE' not in text:
        raise SystemExit(f'Unexpected Horizons reply for {year}:\n{text[:2000]}')
    body = text.split('$$SOE')[1].split('$$EOE')[0]
    rows = []
    for line in csv.reader(io.StringIO(body.strip())):
        stamp, _, _, earth_lon, earth_lat, sun_lon, sun_lat, delta, _, *_ = [c.strip() for c in line]
        date, clock = stamp.split()
        y, mon, d = date.split('-')
        rows.append([f'{y}-{MONTHS[mon]:02d}-{d}T{clock}Z', round(float(earth_lon), 4), round(float(earth_lat), 4),
                     round(float(sun_lon), 4), round(float(sun_lat), 4), round(float(delta)*AU_KM, 1)])
    return rows


def main():
    rows = []
    for year in range(FIRST_YEAR, LAST_YEAR+1):
        part = fetch_year(year)
        if rows and part and part[0][0] == rows[-1][0]:
            part = part[1:]              # each year's request includes the next New Year's midnight
        rows += part
        print(f'{year}: {len(part)} hours', flush=True)
    with gzip.open(OUT, 'wt', newline='', compresslevel=9) as f:
        w = csv.writer(f)
        w.writerow(['utc', 'earth_lon', 'earth_lat', 'sun_lon', 'sun_lat', 'earth_distance_km'])
        w.writerows(rows)
    print(f'Wrote {OUT.name}: {len(rows)} rows, {OUT.stat().st_size/1e6:.2f} MB')


if __name__ == '__main__':
    sys.exit(main())
