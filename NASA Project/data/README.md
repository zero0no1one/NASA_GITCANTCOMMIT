# Real lunar terrain

The default region is a 1.2 km × 1.2 km crop on the **Leibnitz Beta plateau** at **85.4516° S, 31.5491° E**. It comes with coarser layers so that terrain far beyond the crop can block the Sun and Earth, the way it does on the Moon.

## Why this site

The window is chosen for Earth visibility, because a communication dropout only means something if there is a link to lose. At mean libration, Earth's elevation at the centre of each PGDA landing-site tile is:

| PGDA site | Latitude | Earth elevation at mean libration |
|---|---|---|
| 04 Shackleton rim | 89.77° S | −0.5° |
| 01 Connecting ridge | 89.46° S | −0.7° |
| 07 Peak near Shackleton | 88.81° S | −0.9° |
| 11 de Gerlache rim | 88.68° S | +0.2° |
| 23 Malapert massif | 85.99° S | +3.7° |
| 20 Leibnitz Beta plateau | 85.43° S | +3.6° |

Only Sites 20 and 23 keep Earth in the sky at mean libration. Windows on those two tiles were scanned for a flyable default descent onto eligible ground where Earth is clear at the start and lost partway down. At this one, comms drop at 100 s of the 120 s descent, and about half the sampled ground has a view of Earth.

## Files

| File | Size | What it is |
|---|---|---|
| `lola_site20_r1560_c1320.tif` | 0.1 MB | The crop: 240 × 240 px at 5 m/px |
| `lola_site20_r1560_c1320_slope.tif` | 0.2 MB | The same window of PGDA's published slope map (degrees) |
| `lola_site20_surround_40m.tif` | 0.3 MB | The whole 16 km Site 20 tile, averaged to 40 m/px |
| `lola_south_pole_surround_640m.tif` | 1.2 MB | 80–90° S polar mosaic at 640 m/px, rounded to 1 m |
| `lola_site04_r2960_c400.tif`, `_slope.tif`, `lola_site04_surround_40m.tif` | 0.7 MB | A crop near the pole (89.48° S, 156.05° W), kept for comparison. It is not on the crater rim: PGDA names the tile "Shackleton rim", but this window is about 16 km from the crater's centre |

All are south polar stereographic (`+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m`), north-up, with heights in metres.

## Sources

| Data | Product | Reference |
|---|---|---|
| Crops, slope, 40 m layers | NASA GSFC PGDA *South Pole Landing Site LOLA DEMs*, https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/ (Site20 and Site04) | Barker, M. K. et al. (2021). *Improved LOLA elevation maps for south pole landing sites: Error estimates and their impact on illumination conditions.* Planetary and Space Science 203, 105119. doi:10.1016/j.pss.2020.105119 |
| 640 m layer | NASA GSFC PGDA `LDEM_80S_80MPP_ADJ.TIF`, https://pgda.gsfc.nasa.gov/products/90 | Barker, M. K. et al. (2023). *A New View of the Lunar South Pole from LOLA.* Planetary Science Journal 4, 183. doi:10.3847/PSJ/acf3e1 |

## How horizons work

`echo_path/comms.py` first checks each ray against the 5 m crop, then marches it across the coarser layers using only the parts outside finer data. Coarser layers also allow for lunar curvature, which lowers distant ground by d²/2R: about 2.9 km at 100 km away.

**Accuracy check.** For this site I compared the layers against the highest-resolution data available (the 5 m tile, then the 80 m mosaic), using ground and 350 m altitude points, 30 Sun and Earth directions and 3,840 ray checks. The layers disagree on 0.16% of checks, against 2.5% with no surrounding terrain. Near the pole the difference is far larger: at the Site 04 crop, a western Sun at 2° lights 33% of sampled spots with the crop alone and 3% with the full tile.

**Sun and Earth limits** come from `echo_path/astro.py`, using the published extremes: libration of ±6.7° latitude and ±7.9° longitude, and a solar latitude within ±1.54°. At this site that means:

| | Elevation range | App default |
|---|---|---|
| Earth | −3.4° to +10.6° | +3.6° (mean libration), azimuth about 0° (grid north) |
| Sun | up to +6.1° | +4.9°, azimuth 90° |

## Limits

- Sun and Earth are held fixed for a run; they do not yet move during it. The azimuth and elevation sliders stand in for choosing a moment in the lunar day and libration cycle.
- Earth's azimuth stays at its mean. Libration also swings it by about ±8°.
- Shadows used for the rover's route preference check far terrain every 40 m. The sunlight reported along the route checks every point.
- At 5 m/px, boulders and small craters are not resolved.
- Earth at or below 0° counts as blocked, including for a lander high enough to see slightly past the local horizon (about 1° at 350 m).

## Evaluation results

From `NASA Project/`:

```powershell
python -m echo_path.evaluation --dem data/lola_site20_r1560_c1320.tif --surround data/lola_site20_surround_40m.tif --surround data/lola_south_pole_surround_640m.tif --reference-slope data/lola_site20_r1560_c1320_slope.tif
```

With Earth at its mean position this prints:

| Metric | Nominal Flight | Unmitigated Outage | Echo-Path Fallback |
|---|---:|---:|---:|
| Landing hazard score (H) | 0.40 | 1.00 | 0.02 |
| Fuel margin remaining (%) | 79.0 | 79.0 | 75.7 |
| Touchdown slope (deg) | 6.8 | 12.1 | 0.0 |

The paper's "at least 3 fallbacks with H < 0.25 at every dropout" holds for 1 of 5 dropouts here: comms drop late, leaving 11 feasible options at 100 s but only 1 or 2 afterwards.

The computed slope matches the published PGDA slope to within 0.01°. This confirms the engine reproduces the published map, but it is not an independent accuracy check, since both use finite differences on the same grid.

To plan a rover drive:

```powershell
python -m echo_path.rover --dem data/lola_site20_r1560_c1320.tif --surround data/lola_site20_surround_40m.tif --surround data/lola_south_pole_surround_640m.tif --goal 180 1020
```

## Loading it in the dashboards

- **3D app:** this terrain is the default.
- **Streamlit:** choose **Local GeoTIFF path**, enter the full path to the crop, set crop start 0/0, size 240, units **Metres**, and tick the confirmation. Set Earth azimuth to **0°**. Streamlit reads the crop only, so it does not include distant horizons.

## Regenerating or making other crops

```powershell
python data/make_lola_crop.py --site 20 --surround
python data/make_lola_crop.py --site 23 --row 2160 --col 3240 --surround
```

The crop and mosaic read only the bytes they need from the server. The 40 m layer reads the whole site file, so if the connection drops, download the `_surf.tif` and `_slp.tif` by hand and pass `--source-dir <folder>`. Keep committed files small (under about 5 MB).
