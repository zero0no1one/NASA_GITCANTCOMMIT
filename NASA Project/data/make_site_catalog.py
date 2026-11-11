"""Build the curated landing-site list, every coordinate traceable to a NASA or mission source.

South-pole candidates come from NASA GSFC PGDA's surveyed 5 m/px LOLA site tiles: the regions NASA studied as
high-priority landing areas, several of them named Artemis III candidate regions. Each tile is a 16 km square whose
extent is read from the GeoTIFF header over the network, without downloading the file. A tile's centre can fall
in a crater (Shackleton's does), but the sites these regions are named for are rims, ridges and massifs: high
ground. So each site is placed at the highest point of its tile on the 640 m south polar map in this folder, then
moved to the highest point within 1.5 km on PGDA's 80 m polar mosaic, so it sits on the crest rather than beside it.
Past landings come from NSSDC (Apollo) and LROC or NASA (later missions). Coordinates are in the Moon's
mean-Earth/polar-axis frame, east longitude positive.

Run from "NASA Project":  python data/make_site_catalog.py
Writes data/sites_catalog.json.
"""
import json
from pathlib import Path
import numpy as np
import rasterio
from echo_path.astro import grid_to_lat_lon

OUT = Path(__file__).resolve().parent/'sites_catalog.json'
PGDA = 'https://pgda.gsfc.nasa.gov/data/LOLA_5mpp'
PGDA_PAGE = 'https://pgda.gsfc.nasa.gov/products/78'
PGDA_SITES = [('Site01', 'Connecting ridge'), ('SL3', 'Connecting ridge extension'), ('Site04', 'Shackleton rim'),
              ('Site07', 'Peak near Shackleton'), ('Site06', 'Nobile rim 1'), ('DM2', 'Nobile rim 2'),
              ('Site11', 'de Gerlache rim'), ('Site42', 'de Gerlache-Kocher massif'), ('Site20', 'Leibnitz Beta plateau'),
              ('Site23', 'Malapert massif'), ('Haworth', 'Haworth'), ('DM1', 'Amundsen rim'), ('LM7', 'Faustini rim A')]
NSSDC = 'https://nssdc.gsfc.nasa.gov/planetary/lunar/apolloland.html'
LANDED = [
    ('Apollo 11', 'Apollo', .674, 23.473, NSSDC), ('Apollo 12', 'Apollo', -3.013, -23.422, NSSDC),
    ('Apollo 14', 'Apollo', -3.646, -17.472, NSSDC), ('Apollo 15', 'Apollo', 26.132, 3.633, NSSDC),
    ('Apollo 16', 'Apollo', -8.973, 15.501, NSSDC), ('Apollo 17', 'Apollo', 20.191, 30.772, NSSDC),
    ('Chandrayaan-3 (Vikram)', 'Other nations', -69.3741, 32.32, 'https://lroc.im-ldi.com/images/1314'),
    ("Chang'e 4", 'Other nations', -45.4561, 177.5885, 'https://lroc.im-ldi.com/images/1087'),
    ("Chang'e 6", 'Other nations', -41.6385, -153.9852, 'https://lroc.im-ldi.com/images/1374'),
    ('Intuitive Machines IM-1 (Odysseus)', 'Commercial (CLPS)', -80.13, 1.44,
     'https://www.nasa.gov/missions/lro/nasas-lro-images-intuitive-machines-odysseus-lander/'),
    ('Firefly Blue Ghost Mission 1', 'Commercial (CLPS)', 18.5623, 61.8103, 'https://lroc.im-ldi.com/images/1407'),
]


POLAR_MAP = Path(__file__).resolve().parent/'lola_south_pole_surround_640m.tif'
MOSAIC_80M = 'https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF'
CREST_SEARCH_M = 1500.


def tile_bounds(code):
    url = f'/vsicurl/{PGDA}/{code}/{code}_final_adj_5mpp_surf.tif'
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif'):
        with rasterio.open(url) as ds:
            return ds.bounds


def highest_point(raster, bounds):
    """Polar stereographic x, y and height of the highest cell of a raster inside (left, bottom, right, top)."""
    from rasterio.windows import from_bounds
    window = from_bounds(*bounds, transform=raster.transform).round_offsets().round_lengths()
    z = raster.read(1, window=window, boundless=True, fill_value=np.nan, out_dtype='float32').astype(float)
    row, col = divmod(int(np.nanargmax(z)), z.shape[1])
    x, y = raster.window_transform(window)*(col+.5, row+.5)
    return x, y, float(np.nanmax(z))


def main():
    sites = []
    with rasterio.open(POLAR_MAP) as polar, rasterio.open(MOSAIC_80M) as fine:
        for code, name in PGDA_SITES:
            try:
                b = tile_bounds(code)
            except Exception as exc:   # a tile that can't be read is left out rather than guessed
                print(f'skipped {code}: {exc}')
                continue
            x, y, _ = highest_point(polar, b)
            r = CREST_SEARCH_M
            x, y, z = highest_point(fine, (x-r, y-r, x+r, y+r))
            lat, lon = grid_to_lat_lon(x, y)
            centre = grid_to_lat_lon((b.left+b.right)/2, (b.bottom+b.top)/2)
            sites.append({'id': code.lower(), 'name': name, 'group': 'South pole candidates', 'lat': round(lat, 4),
                          'lon': round(lon, 4), 'note': 'Crest of the highest ground in NASA PGDA\'s surveyed 16 km LOLA tile',
                          'tile_centre': [round(centre[0], 4), round(centre[1], 4)], 'source': PGDA_PAGE})
            print(f'{code:7} {name:28} {lat:9.4f} {lon:10.4f}  {z:6.0f} m  (tile centre {centre[0]:.4f}, {centre[1]:.4f})')
    for name, group, lat, lon, source in LANDED:
        sites.append({'id': name.lower().replace(' ', '-').replace("'", '').replace('(', '').replace(')', ''),
                      'name': name, 'group': group, 'lat': lat, 'lon': lon, 'note': 'Landed', 'source': source})
    OUT.write_text(json.dumps({'frame': 'MOON_ME (DE421 mean Earth/polar axis), east longitude positive',
                               'sites': sites}, indent=1)+'\n', encoding='utf-8')
    print(f'Wrote {OUT.name}: {len(sites)} sites')


if __name__ == '__main__':
    main()
