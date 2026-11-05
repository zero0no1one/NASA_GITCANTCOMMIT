"""Build the terrain files for a landing region from NASA GSFC PGDA LOLA products.

Cuts a native-resolution 5 m/px crop of a landing-site DEM and the matching piece of PGDA's
published slope map, then (with --surround) builds the coarser layers used for distant horizons:
the whole site tile at 40 m/px and the 80-90 deg S polar mosaic at 640 m/px.

The crop and the mosaic overview read only the bytes they need from the server. The site tile
layer reads the whole 39-67 MB file; pass --source-dir if the connection drops.

Run from "NASA Project":  python data/make_lola_crop.py --site 20 --surround
"""
import argparse
from datetime import date
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import transform
from rasterio.windows import Window

BASE = 'https://pgda.gsfc.nasa.gov/data/LOLA_5mpp'
MOSAIC = 'https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF'
CRS_XY = '+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs'
LONLAT = '+proj=longlat +R=1737400 +no_defs'
SITES = {'01': 'Connecting ridge', '04': 'Shackleton rim', '07': 'Peak near Shackleton',
         '11': 'de Gerlache rim', '20': 'Leibnitz beta plateau', '23': 'Malapert massif'}
# Windows chosen by scanning the sites with echo_path.comms and echo_path.evaluation.
# Site 20: Earth visible at mean libration, lost at 100 s of the default descent, about half the ground has a view.
# Site 04: close to the pole, kept for comparison; Earth is below the horizon at mean libration.
WINDOWS = {'20': (1560, 1320), '04': (2960, 400)}
TILE_FACTOR = 8      # 5 m -> 40 m
MOSAIC_FACTOR = 8    # 80 m -> 640 m


def site_url(site, product):
    return f'{BASE}/Site{site}/Site{site}_final_adj_5mpp_{product}.tif'


def read_from(url, source_dir=None):
    """Where to read a PGDA file: a local copy if there is one. Files always record the public URL as their source."""
    local = Path(source_dir)/url.rsplit('/', 1)[1] if source_dir else None
    return str(local) if local and local.exists() else url


def write(out, data, crs, tr, nodata, source, **tags):
    predictor = 3 if data.dtype.kind == 'f' else 2
    with rasterio.open(out, 'w', driver='GTiff', width=data.shape[1], height=data.shape[0], count=1, dtype=data.dtype,
                       crs=crs, transform=tr, nodata=nodata, compress='deflate', predictor=predictor, zlevel=9) as dst:
        dst.write(data, 1)
        dst.update_tags(SOURCE_URL=source, CREATED=date.today().isoformat(), **tags)
    print(f'Wrote {out} ({Path(out).stat().st_size/1e6:.2f} MB)')


def crop(url, row, col, size, out, source_dir=None):
    with rasterio.open(read_from(url, source_dir)) as src:
        win = Window(col, row, size, size)
        data = src.read(1, window=win)
        write(out, data, src.crs, src.window_transform(win), src.nodata, url, CROP_ROW=row, CROP_COL=col, CROP_SIZE=size)
        return src.xy(row+size//2, col+size//2)


def site_layer(site, out, source_dir=None):
    url = site_url(site, 'surf')
    with rasterio.open(read_from(url, source_dir)) as src:
        z = src.read(1).astype(float)
        rows, cols = z.shape[0]//TILE_FACTOR, z.shape[1]//TILE_FACTOR
        mean = z[:rows*TILE_FACTOR, :cols*TILE_FACTOR].reshape(rows, TILE_FACTOR, cols, TILE_FACTOR).mean(axis=(1, 3))
        write(out, np.round(mean, 1).astype('float32'), src.crs, src.transform*src.transform.scale(TILE_FACTOR),
              float('nan'), url, DECIMATION=TILE_FACTOR)


def mosaic_layer(out):
    with rasterio.open(MOSAIC) as src:
        shape = (src.height//MOSAIC_FACTOR, src.width//MOSAIC_FACTOR)
        z = src.read(1, out_shape=shape).astype(float)
        data = np.where(np.isfinite(z), np.round(z), -32768).astype('int16')
        write(out, data, src.crs, src.transform*src.transform.scale(MOSAIC_FACTOR), -32768, MOSAIC, DECIMATION=MOSAIC_FACTOR)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--site', default='20', choices=sorted(SITES))
    parser.add_argument('--row', type=int, help='Crop start row in the site DEM (from north)')
    parser.add_argument('--col', type=int, help='Crop start column (from west)')
    parser.add_argument('--size', type=int, default=240, help='Crop size in pixels (the dashboard allows up to 240)')
    parser.add_argument('--out', help='Output DEM path; defaults to data/lola_site<NN>_r<row>_c<col>.tif')
    parser.add_argument('--no-slope', action='store_true', help='Skip the published slope crop')
    parser.add_argument('--surround', action='store_true', help='Also build the 40 m site layer and the 640 m polar layer')
    parser.add_argument('--source-dir', help='Folder holding already-downloaded PGDA site files')
    args = parser.parse_args(argv)
    row, col = WINDOWS.get(args.site, (0, 0))
    row = row if args.row is None else args.row
    col = col if args.col is None else args.col
    here = Path(__file__).parent
    out = Path(args.out or here/f'lola_site{args.site}_r{row}_c{col}.tif')
    x, y = crop(site_url(args.site, 'surf'), row, col, args.size, out, args.source_dir)
    lon, lat = transform(CRS_XY, LONLAT, [x], [y])
    print(f'Centre x={x:.1f} m, y={y:.1f} m; lat {lat[0]:.4f}, lon {lon[0]:.4f}')
    if not args.no_slope:
        crop(site_url(args.site, 'slp'), row, col, args.size, out.with_name(out.stem+'_slope.tif'), args.source_dir)
    if args.surround:
        site_layer(args.site, here/f'lola_site{args.site}_surround_40m.tif', args.source_dir)
        mosaic_layer(here/'lola_south_pole_surround_640m.tif')


if __name__ == '__main__':
    main()
