# Echo-Path 3D

A landing navigator on real lunar terrain: read the coordinates of any point on the Moon, see whether the ground there can be landed on, fly the lander there, then drive the rover. Built with Vite, React, TypeScript and Three.js (via React Three Fiber). All the physics runs in the Python engine (`NASA Project/echo_path/`), served by a small FastAPI app (`NASA Project/api/`).

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

## How it works

**Plan: where to land.** The app ranks landing sites on the terrain by how flat and smooth the ground is and the fuel to reach it, preferring spots with Earth and the Sun in view. Move the cursor over the Moon to read its real latitude and longitude, elevation and slope. Click a spot, or type coordinates under **Go to coordinates**, to check it: the panel says whether it's safe to land and why not if it isn't, and whether Earth and the Sun are in view from there. Then choose **Land here**, and **Begin descent**.

**Descend.** The lander flies the route, gold while it has contact with Earth and dashed orange when terrain blocks the link. The panel shows altitude, descent rate, distance and bearing to the target, and fuel. To change course mid-flight, click a spot and choose **Divert here**: the new route starts from the lander's exact position, velocity and remaining fuel, and the app tells you if it can't get there.

**Drive.** After touchdown the rover drives an A\* route to its goal. Click anywhere to send it there and it turns from where it is now, leaving a dashed trail of where it has been. The route is blue where Earth is in view and orange where it's blocked. The panel shows speed, heading, battery and sunlight, with a speed and battery chart and the timing of each route leg.

**Plan for losing contact**, in the plan panel, lets you simulate losing contact at any moment and choose a precomputed backup site to divert to.

### On the map

- **Layers:** *Surface* shows the terrain lit by the Sun; *Landing safety*, *Slope* and *Height* tint it while keeping the relief visible.
- **Camera:** *Overview*, *Horizon* (a view from the ground with Earth in the sky) and *Follow vehicle*.
- **Realism:** real LOLA elevations at 5 m per pixel, shadows from the Sun's real direction, NASA's surrounding terrain out to the horizon, and the Earth and Sun at their true positions and sizes. Earth's phase comes from the real lighting. The vehicles are drawn 7× life size so they can be seen on a kilometre-wide map, and height is exaggerated 1.5× by default (adjustable).
- **Terrains:** the Leibnitz Beta plateau (default), a site near the pole where Earth is low or hidden, and a synthetic test map where only the map itself can block the Earth or Sun, which the app points out.
- **New random surface:** generates a fresh made-up stretch of Moon, with craters, boulders and sometimes a ridge. The app ranks where to land on it, and the plan screen shows the rover's best route from touchdown to its goal (blue marker) before you fly. Sites the rover couldn't drive away from are marked and ranked last. Each surface has a number, and the same number always gives the same surface.

## Code map

| Path | What it does |
|---|---|
| `src/api.ts` | Response types (mirror `NASA Project/api/main.py`) and fetch helpers |
| `src/coords.ts` | Latitude/longitude conversion, grid sampling, plain-language landing verdicts |
| `src/state.ts` | Zustand store: inputs, flight plan, rover plan, playback clock |
| `src/usePlanner.ts` | Fetches sites and the flight plan, and re-plans the rover when inputs change |
| `src/track.ts` | Builds the flown route and interpolates along it |
| `src/scene/` | Three.js scene: terrain, horizon, sky, coordinate grid, reticle, lander, rover, camera |
| `src/ui/` | Coordinate readout, plan, descent and drive panels, spot inspector, settings, timeline |

Coordinates: the engine uses x = east, y = north, z = up (metres). `scene/geo.ts` maps them to Three.js (x, up, −north), centred on the terrain. `coords.ts` converts them to latitude and longitude using the terrain's south polar stereographic origin.

**Changing terrain responses:** browsers cache them for an hour, so bump `TERRAIN_DATA_VERSION` in `src/api.ts` whenever their fields change.

## Design

Colours come from the subject: true black sky, Kapton foil gold for actions and your route, Earth blue only for the comms link, orange for warnings. Headings and the large coordinate are set in Jost, a descendant of Futura, the typeface on the Apollo 11 plaque. The landing reticle is based on the grid etched on the Apollo Lunar Module window for choosing a landing point. Data is in IBM Plex Sans with tabular figures, so numbers don't jitter as they change.

The layout adapts below 900 px wide: readout, then the Moon, playback, panels and view tools in a single column. Controls are keyboard accessible, and reduced-motion settings are respected.

## Checks

```powershell
npm run lint
npm run build   # TypeScript type-check + production bundle
```

CI runs both on every push and pull request, alongside the Python tests and a container build.
