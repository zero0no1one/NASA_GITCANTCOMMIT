# Echo-Path

Working Streamlit research prototype for lunar descent contingency planning, with a synthetic demo that requires no downloaded data.

## Run

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Alternatively double-click **Start Echo-Path.bat** in this folder. Keep the launcher running; open http://localhost:8501 if the browser does not open automatically. Stop the server with Ctrl+C in its terminal.

Requires Python 3.11+ and the packages in requirements.txt. Verified locally with Python 3.13, Streamlit 1.64, Rasterio 1.5.1, and Plotly 7.1.

## Manual acceptance test

1. Launch the default Synthetic demo. It should show a terrain ridge, nominal route, blocked communication markers and ranked fallback paths. No nominal failure banner should appear.
2. Switch between Elevation, Hazard, Slope and Roughness layers. Axes are in metres and the overlays stay aligned.
3. Open **3D descent** and rotate/zoom the scene. Fallbacks start at the selected outage location and end on terrain.
4. Move the outage selector to an earlier/later state. The fallback routes and rankings should change. At touchdown, no new fallback descent is available.
5. Open **Flight telemetry** to inspect clearance, required thrust, velocity and mass.
6. Open **Outage coverage & export**, click **Precompute all sampled dropouts**, and inspect the per-waypoint option counts. Download the ZIP and inspect mission.json, nominal.csv and outage route CSVs.
7. Change initial propellant to **1 kg**: expect Insufficient fuel, disabled batch planning, no fallback options, and cleared prior coverage. Restore **300 kg**.
8. Change maximum thrust to **100 N**: expect Thrust limit exceeded. Restore **5000 N**.
9. Set Earth/relay elevation to **90 degrees**: locally unobstructed airborne samples should have no terrain-induced blockage. Set it to **-5 degrees**: all communication samples are blocked under the local-horizon approximation. Restore **3 degrees**.
10. Enable **Require sunlit landing sites** and set Sun elevation to **-5 degrees**: expect 0% eligible area and no fallback options. Disable the requirement to restore the baseline.
11. Select **Local GeoTIFF path**, enter a nonexistent file and confirm units: expect a readable load error, not a traceback. Return to Synthetic demo.
12. Once available, upload your LOLA GeoTIFF or enter its path, choose a native-resolution crop, confirm lunar source/vertical units, and inspect its metadata. Missing DEM regions must never become eligible landing sites. A geographic degree raster should be rejected with a reprojection instruction.

## Needed data

Real LOLA data are not bundled. Keep the download's projection, vertical-unit, scale/offset and nodata documentation; retain the accompanying LBL if downloading raw PDS IMG. The current importer expects a north-up projected lunar GeoTIFF with horizontal metres. See MODEL_GUIDE.md for model assumptions and optional vehicle/geometry inputs.

## Automated verification

```powershell
python -m unittest discover -s tests -v
```

Engine tests cover known slope/roughness, nodata, occlusion, analytic hover fuel, thrust/fuel/collision rejection, state-continuous fallbacks and GeoTIFF metadata. Dashboard tests exercise default results, batch computation, parameter changes, coverage invalidation, illumination controls and invalid paths.

## Layout

- app.py: dashboard, plots and ZIP export.
- echo_path/terrain.py: synthetic terrain, cropped GeoTIFF ingestion and hazards.
- echo_path/comms.py: terrain raycasting and illumination.
- echo_path/trajectory.py: polynomial point-mass guidance and feasibility checks.
- echo_path/routing.py: candidate search and ranking from outage state.
- MODEL_GUIDE.md: data contract, equations, limits and reference sources.

Results are sampled prototype feasibility checks, not operational flight plans. Real lunar-data validation remains pending your DEM download.
