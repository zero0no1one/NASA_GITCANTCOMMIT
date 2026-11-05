# Echo-Path

**Live demo: https://nasa-gitcantcommit.onrender.com/** (free hosting: it can take about a minute to wake after 15 idle minutes)

Echo-Path is a research prototype that maps coordinates on the Moon and navigates a vehicle to where the terrain says it can land. Using real NASA LOLA elevation data, it reads the ground at any latitude and longitude, recommends safe landing sites, flies a lander there and can divert it mid-flight, and then drives a rover from wherever it touched down. Along the way it tracks what terrain does to the mission: where the line of sight to Earth is lost, what's in shadow, and what fuel and battery remain.

It is intended for demonstrations and early algorithm development. It is not flight software, an operational mission planner, or proof that a trajectory is safe for a real spacecraft.

## 1. What it does

1. Represents a landing region as an elevation grid, using a 1.2 km crop of NASA LOLA data on the Leibnitz Beta plateau (85.45° S, 31.55° E), with real latitude and longitude for every point.
2. Finds landing hazards from slope, local roughness, missing data and, optionally, sunlight, and explains in plain language why a spot can or can't be landed on.
3. Ranks the best landing sites on the map by flatness, smoothness and fuel, preferring spots with Earth and the Sun in view.
4. Flies a point-mass descent to the chosen target, checking fuel, thrust and terrain clearance, and can re-route from the lander's exact state mid-flight.
5. Finds where terrain blocks the line of sight to Earth during the descent, including terrain up to 186 km away and lunar curvature.
6. From a simulated outage, searches for reachable, hazard-filtered backup landing sites and ranks them.
7. Plans a rover drive with A\* from the touchdown point, then reports time, speed, heading, Earth comms, sunlight and battery along the route. The rover re-plans from where it is whenever the goal or settings change.

## 2. Two ways to use it

| | 3D app (`web/`) | Streamlit dashboard (`NASA Project/app.py`) |
|---|---|---|
| Best for | Choosing where to land and flying there: live coordinates, site ranking, in-flight diverts, rover | Analysis: every lander setting, your own DEMs, batch coverage, ZIP export |
| Terrain | Built-in real sites and a synthetic test map | Synthetic, or any GeoTIFF you load |
| Sun and Earth limits | Only what each site can really see | Free sliders |
| Horizons | Terrain out to 186 km, with lunar curvature | Inside the loaded crop only |
| Rover | Yes | No |

Both use the same Python engine.

## 3. Repository layout

```text
README.md                  This file
CONTRIBUTING.md            Team workflow
DEPLOY.md                  How the live demo is deployed
FEEDBACK.md                Documentation review and open issues
Dockerfile                 Builds the whole site as one service
web/                       3D app: Vite, React, TypeScript, Three.js (see web/README.md)
NASA Project/
├── echo_path/             The engine
│   ├── terrain.py         Synthetic terrain, GeoTIFF loading, hazards, surrounding terrain layers
│   ├── comms.py           Line of sight and shadow raycasting
│   ├── astro.py           Where the Sun and Earth can appear from a site
│   ├── trajectory.py      Point-mass polynomial descent model
│   ├── routing.py         Fallback candidate search and ranking
│   ├── rover.py           A* route, smoothing, timed drive with comms, sunlight and battery
│   ├── evaluation.py      Results table for the paper
│   └── export.py          ZIP export helpers
├── api/                   FastAPI server used by the 3D app
├── data/                  Real terrain files (see data/README.md for sources)
├── tests/                 Automated tests
├── app.py                 Streamlit dashboard
├── requirements.txt       Python dependencies for the dashboard and engine
├── Start Echo-Path.bat    Windows launcher for the dashboard
├── MODEL_GUIDE.md         Dashboard assumptions and equations
├── README.md              Dashboard quick start and acceptance checklist
├── NASA Space Apps Challenge 2026 - Plan.md
├── NASA Space Apps 2026 - Paper.md
└── NASA Space Apps 2026 - Paper corrections (draft).md
```

## 4. Running it

Use Python 3.11 or newer, and Node 20 or newer for the 3D app. Commands start from the repository root.

**3D app** (two terminals):

```powershell
cd "NASA Project"
python -m pip install -r api/requirements.txt
python -m uvicorn api.main:app --reload --port 8000
```

```powershell
cd web
npm install
npm run dev
```

Then open http://localhost:5173. See `web/README.md` for what's on screen and `DEPLOY.md` for the production build.

**Streamlit dashboard:**

```powershell
cd "NASA Project"
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Then open the address it prints, normally http://127.0.0.1:8501. On Windows you can also double-click `Start Echo-Path.bat`. Keep the terminal open while using it; `Ctrl+C` stops it.

**Command-line tools** (from `NASA Project/`):

```powershell
python -m echo_path.evaluation --dem data/lola_site20_r1560_c1320.tif --surround data/lola_site20_surround_40m.tif --surround data/lola_south_pole_surround_640m.tif
python -m echo_path.rover --dem data/lola_site20_r1560_c1320.tif --surround data/lola_site20_surround_40m.tif --surround data/lola_south_pole_surround_640m.tif --goal 180 1020
```

## 5. Results at the default site

These figures use the evaluation's fixed descent target (75% across the map), not the app's top recommended site, which keeps Earth in view for the whole descent. With Earth at its mean position (3.6° elevation), comms on this route are clear until 100 s of the 120 s descent. Full method, sources and accuracy checks are in `NASA Project/data/README.md`.

| Metric | Nominal Flight | Unmitigated Outage | Echo-Path Fallback |
|---|---:|---:|---:|
| Landing hazard score (H) | 0.40 | 1.00 | 0.02 |
| Fuel margin remaining (%) | 79.0 | 79.0 | 75.7 |
| Touchdown slope (deg) | 6.8 | 12.1 | 0.0 |

"Unmitigated" is a constructed scenario: the target is moved to the nearest cell that fails the surface limits but can still be flown to, standing in for a target the ground would have redirected away from. These numbers describe one scenario with illustrative vehicle values, not a statistical result.

Fallback coverage drops as touchdown nears: 11 feasible options at 100 s, then 1–2 at each later dropout.

A rover drive across the map to a goal in the north-west is 836 m in about 39 minutes over 5 legs, with Earth blocked 44% of the time and shadow 24%. That is about 2 minutes quicker than a straight line, because the route avoids steeper ground.

## 6. Models

### Terrain and hazards (`terrain.py`)

`Terrain` stores the elevation array, horizontal spacing, source and metadata. Coordinates are local X/easting and Y/northing in metres, and row zero is the southern edge.

```text
slope  = atan(sqrt((dz/dx)^2 + (dz/dy)^2))          central differences
rough  = RMS departure from a plane fitted over the landing neighbourhood
hazard = clip(0.65*slope/slope_limit + 0.35*rough/roughness_limit, 0, 1)
```

A cell is eligible only when its entire landing neighbourhood is known and within both limits. Map edges and missing cells are excluded, and ineligible cells get a hazard of 1. Sunlight, where required, is a pass/fail filter rather than a weighted term.

### Line of sight (`comms.py`)

`visibility()` marches a ray from each point toward an azimuth and elevation, and terrain above the ray blocks it. Within the crop it uses a local flat surface, at half-cell steps. If the terrain has surroundings, the ray continues across the coarser layers, using each one only outside finer data and lowering distant ground by d²/2R for lunar curvature. An elevation at or below 0° counts as blocked.

`shadow_map()` applies the same idea to every cell. The rover uses a coarser version to steer its route; the sunlight it reports is ray-cast at each point along the drive.

### Sun and Earth limits (`astro.py`)

A simple Moon-fixed geometry using published extremes: libration of about ±6.7° in latitude and ±7.9° in longitude, a solar latitude within ±1.54°, and Earth's small parallax. It gives each site's possible range. It is not a time-resolved ephemeris.

### Descent (`trajectory.py`)

`Vehicle` stores dry mass, fuel, maximum thrust, specific impulse, lunar gravity (1.62 m/s²) and g0 (9.80665 m/s²).

`trajectory()` uses a cubic position polynomial from the initial position and velocity to a stationary touchdown, derives velocity and acceleration analytically, and samples at most 0.5 s and half a cell apart (at least 121 samples, at most 15,000).

```text
m(t) = m(0) exp(-integral(|a - g| dt) / (Isp * g0))
```

A route is rejected if it leaves known terrain, hits terrain, drops below dry mass, exceeds maximum thrust or needs downward thrust. This evaluates a commanded trajectory; it does not simulate a controller.

### Fallback search (`routing.py`)

`plan_fallbacks()` starts from the outage state's exact position, velocity, remaining mass and remaining time. It pre-scores eligible cells by `hazard + 0.25*distance/map_size`, picks up to 16 at least 4 cells apart (always including the nearest), tries three durations (0.8, 1.0 and 1.25 times the remaining time, at least 4 s), and ranks feasible routes by:

```text
score = hazard + 0.4 * fuel_used / available_propellant
```

This is a bounded heuristic search, not a global optimizer or a proof of reachability. "No result" means none of these candidates passed.

### Rover (`rover.py`)

Each cell costs:

```text
cost = 1 + 2*slope/max_slope + rough/max_roughness + shadow_penalty*shadowed
```

Cells over the slope or roughness limit (or with missing data) are blocked. `astar()` is an 8-connected A\* with straight-line distance as its heuristic. `smooth()` then removes grid zig-zags, taking a straight shortcut only where it costs no more than the route it replaces.

`drive()` walks the route with speed `speed*max(0.3, 1 - slope/max_slope)`, and integrates the battery step by step, with charge above full lost. The rover stops if the battery empties. The default speed and power values are illustrative.

### API (`api/main.py`)

| Endpoint | Returns |
|---|---|
| `GET /api/terrains` | Available terrains and each one's sky limits |
| `GET /api/terrain/{id}` | Elevation, hazard and slope grids (cached) |
| `GET /api/terrain/{id}/horizon` | The surrounding landscape, for drawing (cached) |
| `POST /api/sites` | Ranked landing sites with coordinates |
| `POST /api/point` | Ground conditions and Earth and Sun visibility at a spot |
| `POST /api/mission` | Descent to a target, comms samples and ranked backups |
| `POST /api/divert` | A new route from the lander's current state |
| `POST /api/rover` | Rover route, timeline and summary |
| `GET /api/health` | Health check |

If the web app has been built, the API also serves it, so one process is the whole site.

## 7. Streamlit dashboard workflow

**Terrain.** `Synthetic demo` is the default and needs no data: a 101 × 101 grid at 10 m spacing with a ridge, a basin and crater-like depressions. `Upload GeoTIFF` takes a `.tif` or `.tiff`. `Local GeoTIFF path` reads a path on the computer running Streamlit, for example `C:\path\to\lola_crop.tif`. For a real DEM, choose a crop start, crop size and vertical units, and confirm the data is lunar.

**Limits.** Maximum slope and detrended roughness, landing neighbourhood size, and an optional sunlit requirement with Sun azimuth (clockwise from grid north) and elevation.

**Descent and vehicle.** Start and target as percentages of the tile, initial height, descent time, initial velocity, dry mass, propellant, maximum thrust and specific impulse. The defaults are demonstration values, not a real lander.

**Communication.** A fixed direction: azimuth clockwise from grid north and elevation above local horizontal. Rays are checked only inside the crop, and the app says so: "clear" means nothing blocks it within the tile.

**Results.** The outage slider can inject an outage at any of the 31 sampled states, and fallbacks start from that state's exact position, velocity and mass. The tabs are `Mission map`, `3D descent`, `Flight telemetry`, `Outage coverage & export` and `Data & model guide`.

The ZIP export holds `mission.json`, the terrain and hazard layers as CSV, `nominal.csv`, `coverage.json`, ranked routes per outage and a `README.txt`. Each route's time starts at zero.

## 8. DEM data contract

The importer expects a north-up, unrotated, projected lunar GeoTIFF with horizontal coordinates in metres. It rejects geographic latitude/longitude rasters, rotated rasters, invalid crop origins, crops under 10 rows or columns, crops with no valid elevations and regions over 10 km across.

Raw PDS IMG files must first be converted to a projected GeoTIFF. For every real-data run, record the source product and URL, projection, pixel spacing, vertical units, scale and offset, nodata value, crop window and any processing steps. `NASA Project/data/README.md` does this for the bundled data, and `data/make_lola_crop.py` regenerates it.

The lunar-data checkbox is a human confirmation; it does not validate the file.

## 9. Tests

From `NASA Project/`:

```powershell
python -m pip install -r api/requirements.txt
python -m unittest discover -s tests -v
```

The 76 tests cover hazards, line of sight, far terrain and curvature, Sun and Earth geometry, descent physics, fallback search, A\* and smoothing, battery behaviour, GeoTIFF loading, the bundled data, the evaluation, the API and the Streamlit dashboard.

Every push and pull request to `main` also runs lint and a build of the 3D app, then builds the deployable container and tests it under a 512 MB memory limit.

**Manual checks.** For the dashboard, follow the checklist in `NASA Project/README.md`. For the 3D app:

1. Moving the cursor over the Moon updates the large coordinate and the reticle, which turns orange over ground that can't be landed on.
2. Clicking a numbered flag or list row chooses that site; **Begin descent** flies there.
3. Typing `-85.4583` and `31.4883` under **Go to coordinates** and choosing **Divert here** during descent changes course mid-flight without restarting.
4. After touchdown, the rover drives to its goal. Clicking the terrain mid-drive makes it pause briefly, then turn toward the new goal, leaving a dashed trail.
5. Scrubbing back past that re-route shows the rover on its old route.
6. Moving the Earth slider does not restart the run.
7. The **Horizon** camera shows Earth above the lunar horizon. The near-pole terrain shows Earth below the horizon and all samples blocked.

## 10. Known limitations

- Sun and Earth are fixed during a run; there is no time-resolved ephemeris, and no relay satellites.
- No radio link budget, antenna pointing or handover. Comms means geometric line of sight only.
- Earth at or below 0° counts as blocked, even for a lander high enough to see slightly past the local horizon.
- At 5 m/pixel, boulders and small craters are not resolved, and DEM uncertainty is not modelled.
- The lander is a point mass following a polynomial: no attitude, throttle saturation, engine lag, minimum thrust, navigation error or touchdown dynamics. The default descent is a short terminal phase (350 m, 120 s).
- Lander fallbacks come from a bounded candidate search rather than a global optimizer. A\* is used for the rover only.
- Rover power does not depend on slope, solar input does not depend on Sun angle, and there's no thermal model.
- Route checks are sampled, not a continuous collision proof.
- Vehicle and rover values are illustrative, not a real spacecraft.

These limits must be resolved or explicitly bounded before using outputs for any real mission decision.

## 11. Possible next steps

1. Time-resolved Earth and Sun positions from an ephemeris, and relay satellites.
2. Uncertainty margins on slope, roughness, clearance and line of sight.
3. Constrained powered-descent guidance in place of the cubic evaluator, with attitude and throttle limits.
4. Evaluation across many sites and scenarios rather than one.
5. Rover power that depends on slope and Sun angle.

## 12. References

- Barker, M. K. et al. (2023). A New View of the Lunar South Pole from LOLA. *Planetary Science Journal* 4, 183. [Data](https://pgda.gsfc.nasa.gov/products/90)
- Barker, M. K., Mazarico, E., Neumann, G. A. et al. (2021). Improved LOLA elevation maps for south pole landing sites. *Planetary and Space Science* 203, 105119. [Data](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/)
- [NASA Glenn Research Center: Specific impulse](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/specific-impulse/)
- [NASA Glenn Research Center: Ideal rocket equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ideal-rocket-equation/)
- [Rasterio dataset API](https://rasterio.readthedocs.io/en/stable/api/rasterio.io.html)
