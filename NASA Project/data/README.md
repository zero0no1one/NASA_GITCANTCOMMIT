# Real lunar terrain sample

`lola_site04_r2960_c400.tif` is a 1.2 km × 1.2 km crop of real LOLA elevation data from near the lunar south pole. It's small enough (≈176 KB) to keep in the repository and loads in the dashboard without any conversion.

## Source

| | |
|---|---|
| Product | NASA GSFC Planetary Geodesy Data Archive (PGDA), *South Pole Landing Site LOLA DEMs*, Site04 (the "Shackleton rim" site tile) |
| File | `Site04_final_adj_5mpp_surf.tif` (surface height Z) and `Site04_final_adj_5mpp_slp.tif` (published slope) |
| URL | https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site04/ |
| Reference | Barker, M. K. et al. (2021). *Improved LOLA elevation maps for south pole landing sites: Error estimates and their impact on illumination conditions.* Planetary and Space Science 203, 105119. doi:10.1016/j.pss.2020.105119 |
| Reference frame | MOON_ME frame of the JPL DE421 ephemeris |

## Crop

| | |
|---|---|
| Window in the site DEM | rows 2960–3199, columns 400–639 (from the north-west corner) |
| Size | 240 × 240 pixels at 5 m/pixel = 1.2 km × 1.2 km |
| Centre | x = −6397.5 m, y = −14402.5 m, south polar stereographic; **89.4803° S, 156.0495° W** |
| Projection | `+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m` (metres, north-up) |
| Heights | metres, as published (no scale or offset); nodata = NaN, but none in this crop |

The window comes from the PGDA tile named "Shackleton rim". It sits on the surrounding terrain about 16 km from Shackleton's centre, not on the crater rim itself. It was chosen by scanning the tile with `echo_path.evaluation` for a window where the default descent is flyable, the default target is on eligible ground, and Earth is blocked by terrain for part of the descent.

`lola_site04_r2960_c400_slope.tif` is the same window of PGDA's published slope map (degrees). It's used to check the hazard engine's slope calculation.

## Loading it in the dashboard

1. Terrain source: **Local GeoTIFF path**
2. Path: the full path to `NASA Project/data/lola_site04_r2960_c400.tif`. **Upload GeoTIFF** also works.
3. Crop start row/column: **0**, crop size: **240**, elevation units: **Metres**. Tick the lunar-data confirmation.
4. Earth / relay azimuth: **0°**. In this projection, grid north (+y) points toward 0° longitude, the Earth-facing side. Earth's elevation seen from the pole stays within about ±7°; the default 3° works.

## Evaluation results

From `NASA Project/`:

```powershell
python -m echo_path.evaluation --dem data/lola_site04_r2960_c400.tif --earth-az 0 --reference-slope data/lola_site04_r2960_c400_slope.tif
```

This prints:
- the dropout windows;
- fallback coverage at every dropout;
- the paper's Nominal / Unmitigated / Echo-Path results table;
- the slope comparison.

The computed slope matches the published PGDA slope to within 0.01°. This confirms the engine reproduces the published slope map, but it is not an independent accuracy check, since both use finite differences on the same 5 m grid.

## Regenerating or making other crops

```powershell
python data/make_lola_crop.py                                  # this crop, read directly from the PGDA server
python data/make_lola_crop.py --site 23 --row 1000 --col 1000  # another site/window
```

The script reads only the needed rows from the server. If the connection drops, download the site's `_surf.tif` and `_slp.tif` files by hand and pass `--source-dir <folder>`. Keep committed crops small (under about 5 MB). Full site files are 39–67 MB and should stay out of git.
