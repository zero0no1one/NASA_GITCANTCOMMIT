
project: Echo-Path
title: Lunar Descent Fallback-Routing Mission Planning Tool
type: Capstone Project & NASA Space Apps Entry
status: Active Development
stack: Python, NumPy, SciPy, Rasterio, Matplotlib, Streamlit
tags:
  - aerospace
  - pathfinding
  - lunar-landing
  - simulation
  - python
  - capstone
---

# 🚀 Echo-Path: Lunar Descent Fallback-Routing Mission Planning Tool

## 1. Problem & Solution Summary
**Problem:** Lunar landers lack real-time autonomous routing when communication with Earth drops out during descent over high-risk terrain.

**Solution:** A pre-flight mission planning tool that maps lunar topography, simulates signal dropout corridors, and computes safe automated fallback landing trajectories — so that if communication is lost mid-descent, the lander already has a precomputed, hazard-checked fallback path to follow autonomously.

## 2. Objectives
- Ingest real lunar terrain data for a candidate landing region.
- Derive hazard metrics (slope, roughness, shadow) from that terrain.
- Model Earth line-of-sight and identify communication dropout corridors along a descent path.
- Simulate a simplified descent trajectory.
- Generate and rank fallback landing trajectories that remain safe if contact is lost at any point.
- Present everything in a single planning tool a mission planner could actually use.

## 3. Scope (v1)
To keep this achievable, v1 deliberately limits scope:
- One landing region (a few km²), not the whole Moon.
- Point-mass descent dynamics, not full 6-DOF vehicle simulation.
- Static dropout modeling (geometry + terrain occlusion at a point in time), not full orbital-mechanics-driven Earth visibility over a mission timeline.
- Offline/pre-flight computation only — this tool produces fallback plans in advance; it does not run onboard the lander.

*(These can all be extended in later versions once v1 works end to end.)*

---

## 4. Phases, Deliverables & Tools

### Phase 0 — Foundations (Ongoing)
- **Focus:** Learn Python (`numpy`, `scipy`, `matplotlib`, `rasterio`/GDAL), basic orbital mechanics, coordinate frames (selenographic lat/lon ↔ Cartesian), DEM basics.
- **Deliverable:** Comfort reading/writing basic numpy array and raster-processing code.

### Phase 1 — Terrain Data Pipeline
- **Focus:** Download a LOLA DEM tile for the chosen region from PDS Geosciences Node or USGS Lunar QuickMap. Load it with `rasterio`.
- **Deliverable:** A script that loads the DEM and outputs an elevation heatmap.
- **Tools:** Python, `rasterio`/GDAL, `matplotlib`.

### Phase 2 — Hazard Mapping
- **Focus:** Compute per-cell slope and roughness from the DEM (numpy gradient / neighborhood analysis). Combine into a single hazard score per grid cell.
- **Deliverable:** A hazard map overlay on the terrain (safe/moderate/unsafe zones).
- **Tools:** `numpy`, `scipy.ndimage`, `matplotlib`.

### Phase 3 — Communication Dropout Modeling
- **Focus:** For a chosen descent path, compute line-of-sight to Earth (or relay) at each waypoint via ray-terrain intersection against the DEM. Flag blocked waypoints.
- **Deliverable:** A "dropout corridor" overlay showing where communication would be lost.
- **Tools:** `numpy` raycasting against the DEM grid; basic vector geometry.

### Phase 4 — Descent Trajectory Simulator
- **Focus:** Build a point-mass simulator (position, velocity, thrust, gravity) with a simple guidance law (e.g., constant deceleration) to generate a physically plausible nominal trajectory.
- **Deliverable:** A simulated trajectory (state vector over time) plotted over the terrain.
- **Tools:** `numpy` / `scipy` ODE solvers (`scipy.integrate.solve_ivp`).

### Phase 5 — Fallback Route Selection
- **Focus:** At each dropout-risk waypoint, use the hazard map to precompute the best reachable safe landing zone given the remaining fuel budget. Rank candidates by safety margin and distance.
- **Deliverable:** For each dropout point, a ranked list of fallback trajectories/landing sites.
- **Tools:** A specific path-planning algorithm ($A^*$ or RRT) over the hazard grid and a simple scoring/ranking function.

### Phase 6 — Integration & Presentation
- **Focus:** Combine Phases 1–5 into one tool: load region → show terrain/hazard/dropout overlays → show nominal trajectory → show fallback options at each risk point.
- **Deliverable:** A working demo (Streamlit dashboard or Jupyter Notebook).
- **Tools:** Streamlit, `matplotlib`, `plotly`.

---

## 5. Suggested Timeline (Part-Time Pace)

| Phase | Focus | Rough Duration |
| :--- | :--- | :--- |
| **0** | Foundations | Ongoing, ~1–2 weeks upfront |
| **1** | Terrain data pipeline | 1 week |
| **2** | Hazard mapping | 1 week |
| **3** | Dropout modeling | 1–2 weeks |
| **4** | Descent simulator | 2 weeks |
| **5** | Fallback route selection | 2 weeks |
| **6** | Integration & demo | 1–2 weeks |
| **Total**| **End-to-End Build** | **8–12 weeks part-time** |

*(Note: Phases 3 and 5 are conceptually the hardest and may take longer.)*

---

## 6. Key Data & Reference Sources
- **LOLA DEM data:** PDS Geosciences Node, USGS Astrogeology Lunar QuickMap.
- **Reference program:** NASA's ALHAT (Autonomous Landing Hazard Avoidance Technology) — published papers serve as a spec sheet for the problem.
- **Orbital mechanics reference:** *Orbital Mechanics for Engineering Students* (Curtis).

## 7. Risks & Mitigations
- **Scope creep toward full-fidelity simulation:** Stick to point-mass dynamics until v1 works end to end.
- **DEM files too large to iterate quickly:** Crop to a small region early.
- **Dropout modeling becoming an orbital-mechanics rabbit hole:** Start with static/geometric occlusion; add time-varying Earth position later.
- **No physics/aerospace background:** Lean on ALHAT papers and existing landing-hazard-avoidance literature rather than deriving everything from scratch.

## 8. v1 Success Criteria
Point to one landing region and show, end to end:
1. Its terrain and hazard map.
2. A nominal descent trajectory over it.
3. Where along that trajectory communication would drop out.
4. For each dropout point, at least one computed safe fallback landing option.

---

## 9. Designing v1 for Easy Upgrades Later
v1 stays scoped to one lunar region with static, geometry-based comms modeling. A modular structure ensures upgrades (Mars, live orbital comms, web UI) are additive, not rewrites.

### Module Structure
- `terrain/`: DEM loading + hazard scoring (`load_dem(region)`, `compute_hazard_map(dem)`).
- `comms/`: Dropout modeling behind a shared interface (`get_dropout_corridor(trajectory, terrain)`).
- `trajectory/`: The descent simulator, kept independent of terrain/comms.
- `routing/`: Fallback selection behind a shared interface (`select_fallback(hazard_map, dropout_points, constraints)`).
- `ui/`: Presentation only (Streamlit or Jupyter).
- `config/`: Celestial body, region, and vehicle parameters stored as data (config file), not hardcoded constants.

### Core Architecture Habits
- Never inline body-specific constants (gravity, radius) — pull from config.
- Keep computation and visualization strictly separate.
- Add small sanity checks per module.

### Future Upgrade Paths
- **Add Mars:** A new `mars.py` under `terrain/` + Mars DEM source.
- **Live-Ephemeris Comms:** A new implementation of the `comms/` interface.
- **Learned/AI-Driven Fallback Planner:** A new implementation behind the `routing/` interface, benchmarked against the v1 $A^*$ baseline.

---

## 10. Pitch, Defense & Selling Points (The "Why It Wins" Narrative)
- **The Missing Bridge:** While NASA has real-time obstacle dodgers (ALHAT/SPLICE) and commercial landers have nominal guidance solvers, Echo-Path unifies them into a *pre-flight telemetry-triggered fallback planner*.
- **Determinism over AI:** Mission-critical flight software requires 100% traceable, mathematically verifiable behavior. Using explicit numerical solvers (`SciPy`) and heuristic graph search ($A^*$) over black-box Machine Learning makes this architecture highly realistic for aerospace adoption.
- **NASA Data & Utility:** Directly ingests USGS/PDS LRO LOLA DEM GeoTIFFs to solve the real-world operational risk of late-stage fuel starvation and telemetry loss near lunar craters.