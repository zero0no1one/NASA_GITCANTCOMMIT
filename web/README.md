# Echo-Path 3D

Interactive 3D lander + rover simulation built with Vite, React, TypeScript and Three.js (via React Three Fiber). All the physics runs in the Python engine (`NASA Project/echo_path/`), served by a small FastAPI app (`NASA Project/api/`). The Streamlit dashboard (`NASA Project/app.py`) still works on its own.

## Run it

You need Python 3.11+ and Node 20+. Use two terminals.

**1. API** (from the repository root):

```powershell
cd "NASA Project"
python -m pip install -r api/requirements.txt
python -m uvicorn api.main:app --reload --port 8000
```

**2. Web app:**

```powershell
cd web
npm install
npm run dev
```

Open http://localhost:5173. The dev server forwards `/api/...` to port 8000, so both must be running.

## What you see

- **Terrain:**
  - the real LOLA south-pole crop (default) or the synthetic ridge;
  - coloured by landing hazard, slope or elevation;
  - vertical exaggeration is adjustable.
- **Lander descent:**
  - the nominal route (dashed blue);
  - comms samples (red = blocked by terrain), with the selected outage shown in white;
  - the three ranked fallback routes and touchdown pads.
  - The white cone flies the nominal route until the outage, then the selected touchdown route.
- **Rover traverse:**
  - after touchdown the rover drives an A\* route to the goal (orange pole);
  - the route is coloured by Earth line of sight (blue = clear, red = blocked);
  - the HUD shows mission time, speed, heading, battery, comms and sunlight;
  - the panel at the bottom charts speed and battery (grey bands = shadow) and lists each route leg with timestamps, heading and average speed.
- **Real-time re-routing:**
  - click anywhere on the terrain, or change goal, speed, max slope or Sun direction;
  - the rover re-plans *from where it is now* and steers onto the new route;
  - the ground already driven stays as a dashed trail.

## Code map

| Path | What it does |
|---|---|
| `src/api.ts` | Response types (mirror `NASA Project/api/main.py`) and fetch helpers |
| `src/state.ts` | Zustand store: inputs, mission, rover plan, playback clock |
| `src/usePlanner.ts` | Fetches the mission, and re-plans the rover when inputs change |
| `src/track.ts` | Time interpolation along lander and rover timelines |
| `src/scene/` | Three.js scene: terrain mesh, lander paths, rover model, camera |
| `src/ui/` | HUD, control panel, timeline chart and leg table |

Coordinates: the engine uses x = east, y = north, z = up (metres). `scene/geo.ts` maps them to Three.js (x, up, −north), centred on the terrain.

## Checks

```powershell
npm run lint
npm run build   # TypeScript type-check + production bundle
```

CI runs both on every push and pull request, alongside the Python tests.
