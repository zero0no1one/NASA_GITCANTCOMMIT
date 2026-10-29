# Echo-Path Project Documentation

Echo-Path is a Streamlit research prototype for pre-flight lunar descent contingency planning. It loads a local lunar digital elevation model (DEM) or generates a synthetic test terrain, computes landing hazards, simulates a nominal descent, models terrain-related communication loss, searches for fallback landing sites, and exports reproducible mission data.

The prototype is intended for manual testing, classroom demonstrations, and early algorithm development. It is not flight software, an operational mission planner, or proof that a trajectory is safe for a real spacecraft.

## 1. Project goals

The project addresses the planning problem created by telemetry loss during lunar descent:

1. Represent a candidate lunar landing region as an elevation grid.
2. Identify landing hazards from slope, local roughness, missing data, and optional illumination.
3. Simulate a nominal point-mass descent to a selected landing target.
4. Identify terrain-blocked communication samples along that descent.
5. Start from an outage state and search for reachable, hazard-filtered fallback landing sites.
6. Show the results interactively and export the state, terrain, metrics, and routes.

The current version uses a modular numerical core and a Streamlit interface so each model can be replaced or improved independently.

## 2. Current capabilities

The working prototype provides:

- Synthetic terrain with a ridge, basin, and crater-like depressions.
- GeoTIFF DEM upload and local file path loading.
- Native-resolution DEM crops up to 240 pixels per side in the interface.
- Projected metre-based raster validation.
- Nodata handling, raster scale/offset handling, and elevation unit conversion.
- Slope and detrended roughness maps.
- Landing eligibility filtering by slope, roughness, map boundary, and missing data.
- Optional static Sun-direction shadow filtering.
- Cubic nominal and contingency position guidance.
- Lunar gravity, mass depletion, propellant, and thrust-limit checks.
- Terrain collision and outside-known-terrain checks.
- Static terrain raycasting for Earth or relay line-of-sight.
- Manual outage selection at 31 sampled nominal descent states.
- Batch fallback evaluation for blocked airborne communication samples.
- Ranked fallback route table and 2D/3D visualization.
- ZIP export containing inputs, maps, telemetry, routes, rankings, and coverage results.
- Automated engine and dashboard tests.

## 3. Repository layout

```text
NASA Project/
├── app.py                         Streamlit user interface and orchestration
├── echo_path/
│   ├── __init__.py                Package marker
│   ├── terrain.py                 Synthetic terrain, GeoTIFF loading, hazards
│   ├── comms.py                   Terrain visibility and shadow raycasting
│   ├── trajectory.py              Point-mass polynomial descent model
│   ├── routing.py                 Fallback candidate search and ranking
│   └── export.py                  ZIP export helpers
├── tests/
│   ├── test_engines.py            Numerical and data-ingestion tests
│   └── test_dashboard.py          Streamlit interaction tests
├── requirements.txt               Python dependencies
├── Start Echo-Path.bat            Windows launcher
├── MODEL_GUIDE.md                 Detailed assumptions and equations
├── README.md                      Quick start and acceptance checklist
├── NASA Space Apps Challenge 2026 - Plan.md
└── NASA Space Apps 2026 - Paper.md
```

Python cache folders such as `__pycache__` are generated automatically and are not part of the application design.

## 4. Installation and startup

Use Python 3.11 or newer. Open PowerShell in the project folder:

```powershell
cd "C:\Users\Christian\Documents\NASA Space Apps\NASA Project"
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the address printed by Streamlit, normally:

```text
http://127.0.0.1:8501
```

On Windows, double-click `Start Echo-Path.bat`. Keep the terminal open while using the application; closing it stops the local server. Press `Ctrl+C` in that terminal to stop it.

## 5. Interface workflow

### 5.1 Choose terrain

`Synthetic demo` is the default and requires no external data. It creates a 101 × 101 grid with 10 m spacing, a ridge crossing the region, a basin, and crater-like depressions.

`Upload GeoTIFF` accepts a `.tif` or `.tiff` through the browser.

`Local GeoTIFF path` reads a path on the computer running Streamlit. Enter the full path, for example:

```text
C:\Users\Christian\Downloads\lola_crop.tif
```

For a real DEM, choose a crop start row and column, a crop size, and the elevation unit conversion. Confirm that the file contains lunar elevation data before processing.

### 5.2 Set landing limits

- Maximum slope controls the allowable local terrain angle.
- Maximum detrended roughness controls allowable local height variation.
- Landing neighbourhood controls the approximate lander footprint used for eligibility erosion.
- Require sunlit landing sites enables a static Sun raycast.
- Sun azimuth is measured clockwise from local grid north.
- Sun elevation at or below the local horizon produces no sunlit landing sites in the model.

### 5.3 Set descent and vehicle values

The interface accepts:

- Start and target positions as percentages of the selected tile.
- Initial altitude above the local terrain.
- Nominal descent duration.
- Initial X, Y, and vertical velocity.
- Dry mass and initial propellant mass.
- Maximum thrust.
- Specific impulse.

The default values are demonstration values, not a real lander configuration.

### 5.4 Set communication geometry

Communication is represented by a fixed ray direction:

- Earth/relay azimuth is clockwise from local grid north.
- Earth/relay elevation is the ray angle above the local horizontal.
- Elevation at or below zero is treated as blocked.
- Rays are evaluated only inside the selected DEM crop.

The app labels terrain outside the crop as unknown rather than assuming it is clear.

### 5.5 Inspect results

The summary reports:

- Landing-eligible area.
- Number of blocked communication samples out of 31.
- Nominal propellant required.
- Peak required thrust.

The selected outage slider allows a user to inject an outage at any sampled state, including a normally clear state. The displayed fallback options start at the selected state’s exact position, velocity, and remaining mass.

The tabs provide:

- `Mission map`: elevation, hazard, slope, or roughness with nominal and fallback overlays.
- `3D descent`: terrain surface and route traces in three dimensions.
- `Flight telemetry`: nominal clearance, thrust, mass, velocity, and sampled state table.
- `Outage coverage & export`: batch analysis and downloadable ZIP output.
- `Data & model guide`: input contract, equations, assumptions, and limitations.

## 6. DEM data contract

The importer expects a north-up, unrotated, projected lunar GeoTIFF with horizontal coordinates in metres. Geographic degree grids are rejected because the local gradient and distance calculations require metric spacing.

Before importing LOLA data, record:

- The source product and landing-region coordinates.
- Projection and lunar radius or datum assumptions.
- Horizontal units and pixel spacing.
- Vertical units.
- Band scale and offset.
- Nodata value.
- The original PDS label if the source is a raw IMG/LBL product.
- The processing or reprojection steps used to create the GeoTIFF.

Raw PDS IMG files are not accepted directly by the interface. Convert them to a north-up projected GeoTIFF while preserving the label metadata. Do not select `Kilometres` unless the elevation values supplied to the importer are in kilometres after raster scale and offset are applied.

The importer rejects:

- Geographic latitude/longitude rasters.
- Rotated rasters.
- Invalid crop origins.
- Crops with fewer than 10 rows or columns.
- Crops with no valid elevation values.
- Regions larger than 10 km in either local dimension.

The user must verify that the DEM is lunar data; the checkbox is an intentional human confirmation and does not validate the file scientifically.

## 7. Computational architecture

### 7.1 `terrain.py`

`Terrain` stores the elevation array, horizontal spacing, source name, and metadata. Coordinates are local X/easting and Y/northing in metres. Internally, row zero is the southern edge after imported rasters are flipped from their usual north-first storage order.

`synthetic()` generates the reproducible default terrain from a seed.

`load_dem()` reads a raster crop with Rasterio, applies band scale and offset, applies the selected vertical unit conversion, preserves nodata as `NaN`, validates projection and orientation, and stores source metadata.

`hazards()` computes:

```text
slope = atan(sqrt((dz/dx)^2 + (dz/dy)^2))
```

in degrees, then computes local detrended roughness. A cell is eligible only when its entire landing neighbourhood is known and remains below the slope and roughness thresholds. Map boundaries and missing cells are excluded by erosion.

### 7.2 `comms.py`

`visibility()` samples a ray from each state toward the configured azimuth and elevation. A known terrain value above the ray blocks communication. Missing cells produce unknown coverage unless a known obstacle blocks first. A below-horizon ray is blocked.

`shadow_map()` applies the same ray concept to every terrain cell for optional illumination filtering.

This is a static local geometric model. It does not calculate lunar curvature, orbital ephemerides, relay positions, radio link budget, antenna pointing, or time-varying lighting.

### 7.3 `trajectory.py`

`Vehicle` stores:

```text
dry_mass, fuel, max_thrust, isp, gravity=1.62 m/s², g0=9.80665 m/s²
```

`trajectory()` uses a cubic position polynomial with initial position and velocity and a stationary touchdown endpoint. It analytically derives velocity and acceleration and samples the result at no more than 0.5 seconds per step, with an additional cell-scale sampling bound.

Required acceleration includes lunar gravity. The model estimates propellant from integrated required acceleration:

```text
m(t) = m(0) exp(-integral(required_acceleration dt) / (Isp * g0))
```

The route is rejected if it:

- Leaves known terrain.
- Intersects terrain.
- Drops below dry mass.
- Exceeds maximum thrust.
- Requires downward thrust under the current sign convention.

This is an analytical commanded-trajectory evaluator. It does not simulate a saturated throttle controller, attitude dynamics, engine lag, throttle quantization, structural loads, or navigation uncertainty.

### 7.4 `routing.py`

`plan_fallbacks()` receives the selected nominal state, not only a map coordinate. It uses the exact position, velocity, remaining mass, and time available after the outage.

It selects up to 16 spatially separated eligible landing cells, evaluates three duration factors—0.8, 1.0, and 1.25 times the remaining nominal time—and keeps feasible routes. A candidate score is:

```text
score = landing_hazard + 0.4 * fuel_used / available_mass
```

The nearest eligible site is always evaluated so late outages can still be checked. The planner is a bounded heuristic search, not an A* implementation, a global optimizer, or a proof of reachability.

### 7.5 `export.py`

`export_bundle()` creates a ZIP containing:

- `mission.json`: mission parameters and terrain metadata.
- `elevation_m.csv`: selected elevation crop.
- `hazard.csv`, `slope.csv`, `roughness.csv`, `safe.csv`: analysis layers.
- `nominal.csv`: nominal position, velocity, mass, thrust, and clearance samples.
- `coverage.json`: batch outage coverage and rejection counts.
- `outage_<index>/ranking.json`: ranked candidates per outage state.
- `outage_<index>/route_<rank>.csv`: fallback telemetry for each accepted route.
- `README.txt`: coordinate, time, and interpretation notes.

Each route’s time starts at zero. The outage time is recorded in the mission configuration and coverage table.

## 8. Automated tests

Run the full suite with:

```powershell
python -m unittest discover -s tests -v
```

The tests cover:

- Planar slope and detrended roughness.
- Missing-data exclusion.
- Ridge-based line-of-sight blockage.
- Unknown communication through missing terrain.
- Analytic hover mass depletion.
- Fuel and thrust rejection.
- Terrain collision and outside-tile rejection.
- Synthetic end-to-end fallback generation.
- GeoTIFF projection, orientation, scale, offset, nodata, and metadata.
- Geographic DEM rejection.
- Oversized landing-footprint exclusion.
- ZIP integrity and exported state continuity.
- Streamlit default rendering.
- Batch coverage generation.
- Coverage reset after parameter changes.
- Illumination controls.
- Invalid DEM path handling.

Warnings from Rasterio about future affine-matrix syntax do not indicate a test failure.

## 9. Manual acceptance test

1. Start the app in Synthetic demo mode.
2. Confirm the dashboard shows a ridge, a nominal route, blocked communication markers, and ranked fallbacks.
3. Switch through all four map layers and verify that route overlays remain aligned.
4. Open the 3D descent tab and rotate the plot.
5. Move the outage slider and confirm the fallback ranking changes.
6. Move it to touchdown and confirm that no new descent route is offered.
7. Inspect clearance, thrust, velocity, and mass in Flight telemetry.
8. Run batch outage precomputation and inspect option counts and rejection reasons.
9. Download the ZIP and verify the CSV and JSON files.
10. Set propellant to 1 kg and confirm an insufficient-fuel rejection.
11. Set maximum thrust to 100 N and confirm a thrust-limit rejection.
12. Enable Sun constraints and set Sun elevation to -5 degrees; eligible area should become zero.
13. Enter an invalid local DEM path and confirm a readable load error.
14. Import a valid projected lunar GeoTIFF crop when available.

## 10. Known limitations

The current prototype does not model:

- Lunar curvature or a full selenographic coordinate frame.
- A real Earth, relay, Sun, or lander ephemeris.
- Radio link budgets, antenna attitude, or relay handover.
- DEM uncertainty or vertical datum uncertainty.
- Boulders and hazards smaller than the DEM resolution.
- A full 3-DOF or 6-DOF rigid-body simulation.
- Throttle saturation and attitude control.
- Engine ignition delay or minimum thrust.
- Fuel reserves, landing gear geometry, or touchdown dynamics.
- A* or RRT graph routing.
- A formal continuous-time collision proof.
- Onboard execution or flight certification.

These limitations are deliberate scope boundaries for the first demonstrable prototype. They must be resolved or explicitly bounded before using outputs for any real mission design decision.

## 11. Recommended next upgrades

1. Add a proper lunar coordinate adapter and a documented DEM reprojection pipeline.
2. Add a PDS IMG/LBL conversion utility with provenance logging.
3. Replace static communication geometry with time-tagged Earth and relay ephemerides.
4. Add uncertainty margins to slope, roughness, clearance, and communication rays.
5. Implement a grid-based A* planner with turn, acceleration, and fuel costs.
6. Replace the cubic feasibility evaluator with a constrained dynamics solver.
7. Add lander attitude, thrust-vector, throttle, and minimum-thrust constraints.
8. Add scenario comparison against a nominal-only landing plan.
9. Store mission inputs and exported results in a versioned run manifest.
10. Validate against an agreed LOLA landing-region dataset and published reference cases.

## 12. Data provenance and reproducibility

For every real-data run, save the downloaded source name, source URL or archive identifier, PDS label, projection method, crop window, scale/offset, vertical units, nodata value, app version, parameter values, and exported ZIP. Synthetic terrain is reproducible from its seed.

The export bundle is the intended handoff artifact for a run. It preserves the numerical layers and telemetry needed to reproduce plots and inspect the selected state without relying on the live Streamlit session.

## 13. References

- [NASA Glenn Research Center: Specific impulse](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/specific-impulse/)
- [NASA Glenn Research Center: Ideal rocket equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ideal-rocket-equation/)
- [Rasterio dataset API](https://rasterio.readthedocs.io/en/stable/api/rasterio.io.html)
- `NASA Space Apps Challenge 2026 - Plan.md` in this project
- `NASA Space Apps 2026 - Paper.md` in this project
