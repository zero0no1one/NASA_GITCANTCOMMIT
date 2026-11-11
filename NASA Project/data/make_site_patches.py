"""Cut 80 m/px terrain patches around each south-pole site in sites_catalog.json, for sharper nearby skylines.

The 640 m polar map smooths ridges a few kilometres away, which can put a site's skyline several degrees too low.
Each patch is a 24 km square of NASA GSFC PGDA's 80 m south polar LOLA mosaic, read straight from the server (only
the bytes needed). The horizon code uses a patch where it covers a point, then the 640 m map, then the global map.

Run from "NASA Project":  python data/make_site_patches.py
Writes data/site_patches_80m.npz.
"""
import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from echo_path.horizon import _polar_xy

HERE = Path(__file__).resolve().parent
MOSAIC = 'https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF'
HALF_WIDTH_M = 12_000.
OUT = HERE/'site_patches_80m.npz'


def main():
    sites = [s for s in json.loads((HERE/'sites_catalog.json').read_text(encoding='utf-8'))['sites'] if s['lat'] < -79.5]
    ids, origins, patches = [], [], []
    with rasterio.open(MOSAIC) as src:
        for s in sites:
            x, y = _polar_xy(s['lat'], s['lon'])
            window = from_bounds(x-HALF_WIDTH_M, y-HALF_WIDTH_M, x+HALF_WIDTH_M, y+HALF_WIDTH_M,
                                 transform=src.transform).round_offsets().round_lengths()
            # Sites near 80° S reach past the mosaic's edge; that part is left as no-data.
            z = src.read(1, window=window, boundless=True, fill_value=np.nan, out_dtype='float32').astype(float)
            tr = src.window_transform(window)
            # Store south-up like Echo-Path's grids: row 0 is the southern edge, at the south-west pixel centre.
            sw_x, sw_y = tr*(.5, z.shape[0]-.5)
            ids.append(s['id'])
            origins.append([sw_x, sw_y, tr.a])
            patches.append(np.flipud(np.where(np.isfinite(z), np.round(z), -32768)).astype('int16'))
            print(f"{s['id']:8} {s['name']:28} {z.shape} {np.nanmin(z):7.0f} to {np.nanmax(z):6.0f} m")
    np.savez_compressed(OUT, ids=np.array(ids), origins=np.array(origins), z=np.stack(patches), source=np.array(MOSAIC))
    print(f'Wrote {OUT.name} ({OUT.stat().st_size/1e6:.2f} MB)')


if __name__ == '__main__':
    main()
