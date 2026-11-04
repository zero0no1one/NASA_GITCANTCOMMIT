"""Cut a small native-resolution crop from a NASA GSFC PGDA 5 m/px LOLA landing-site DEM.

Reads only the needed rows straight from the PGDA server, so the full 39 MB site file
is never downloaded. Writes a GeoTIFF the dashboard accepts as-is (projected metres,
north-up), plus the matching crop of PGDA's published slope map for validation.

Run from "NASA Project":  python data/make_lola_crop.py
"""
import argparse
from datetime import date
from pathlib import Path
import rasterio
from rasterio.warp import transform
from rasterio.windows import Window

BASE = 'https://pgda.gsfc.nasa.gov/data/LOLA_5mpp'
CRS_XY = '+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs'
LONLAT = '+proj=longlat +R=1737400 +no_defs'
SITES = {'01': 'Connecting ridge', '04': 'Shackleton rim', '07': 'Peak near Shackleton',
         '11': 'de Gerlache rim', '20': 'Leibnitz beta plateau', '23': 'Malapert massif'}
# Chosen by scanning the site with echo_path.evaluation: flyable nominal descent onto
# eligible ground, with Earth (grid north, 3 deg elevation) blocked from 84 s onward.
DEFAULT_ROW, DEFAULT_COL = 2960, 400


def site_url(site, product, source_dir=None):
    name = f'Site{site}_final_adj_5mpp_{product}.tif'
    return str(Path(source_dir)/name) if source_dir else f'{BASE}/Site{site}/{name}'


def crop(url, row, col, size, out):
    with rasterio.open(url) as src:
        win = Window(col, row, size, size)
        data = src.read(1, window=win)
        profile = {'driver': 'GTiff', 'width': size, 'height': size, 'count': 1, 'dtype': data.dtype,
                   'crs': src.crs, 'transform': src.window_transform(win), 'nodata': src.nodata,
                   'compress': 'deflate'}
        centre = src.xy(row+size//2, col+size//2)
    with rasterio.open(out, 'w', **profile) as dst:
        dst.write(data, 1)
        dst.update_tags(SOURCE_URL=url, CROP_ROW=row, CROP_COL=col, CROP_SIZE=size,
                        CREATED=date.today().isoformat())
    return centre


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--site', default='04', choices=sorted(SITES))
    parser.add_argument('--row', type=int, default=DEFAULT_ROW, help='Crop start row in the site DEM (from north)')
    parser.add_argument('--col', type=int, default=DEFAULT_COL, help='Crop start column (from west)')
    parser.add_argument('--size', type=int, default=240, help='Crop size in pixels (the dashboard allows up to 240)')
    parser.add_argument('--out', help='Output DEM path; defaults to data/lola_site<NN>_r<row>_c<col>.tif')
    parser.add_argument('--no-slope', action='store_true', help='Skip the published slope crop')
    parser.add_argument('--source-dir', help='Folder holding already-downloaded PGDA site files, '
                                             'if reading from the server fails')
    args = parser.parse_args(argv)
    out = Path(args.out or Path(__file__).with_name(f'lola_site{args.site}_r{args.row}_c{args.col}.tif'))
    x, y = crop(site_url(args.site, 'surf', args.source_dir), args.row, args.col, args.size, out)
    lon, lat = transform(CRS_XY, LONLAT, [x], [y])
    print(f'Wrote {out} (centre x={x:.1f} m, y={y:.1f} m; lat {lat[0]:.4f}, lon {lon[0]:.4f})')
    if not args.no_slope:
        slope_out = out.with_name(out.stem+'_slope.tif')
        crop(site_url(args.site, 'slp', args.source_dir), args.row, args.col, args.size, slope_out)
        print(f'Wrote {slope_out}')


if __name__ == '__main__':
    main()
