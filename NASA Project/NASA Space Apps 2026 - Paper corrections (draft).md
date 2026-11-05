# Echo-Path Paper: Proposed Corrections (Draft for Review)

**This is a draft for the paper's authors to review. Nothing in `NASA Space Apps 2026 - Paper.md` has been changed.** Section numbers match the paper, and each section below can replace the one with the same number.

Every number here comes from the current code and can be reproduced with the commands in §8. Every reference was checked against a library or publisher record.

## Decisions needed before using this

| # | Decision | Default used in this draft |
|---|---|---|
| 1 | Which Space Apps 2026 challenge does this answer? | Left as `[challenge name]` |
| 2 | Who are the authors? | Left for the team |
| 3 | Why does losing comms matter? (see §3) | Losing the link removes ground oversight and any late retargeting, so vetted alternatives must already be on board |
| 4 | Is the "Unmitigated Outage" scenario acceptable? (see §8.3) | Yes, clearly labelled as a constructed scenario |
| 5 | Project title | Option B, which fits a planning tool and doesn't claim autonomy |
| 6 | Does the paper need to disclose AI assistance? | Check the current Space Apps rules |

---

## Title

**Echo-Path: A Modular Pre-Flight Planning Framework for Lunar Landing Contingency and Rover Traverse**

*Remove the subtitle's "Autonomous Contingency Routing in Unconstrained Lunar Terrain": nothing runs autonomously on a vehicle, and "unconstrained" isn't accurate.*

## 2. Abstract

When a lunar lander's line of sight to Earth is blocked by terrain during descent, the ground loses its view of the vehicle and any chance to change the plan. This paper presents Echo-Path, a pre-flight planning prototype that identifies where this happens and prepares alternatives in advance. Using NASA Lunar Orbiter Laser Altimeter (LOLA) terrain at 5 m/pixel, it maps landing hazards from slope and roughness, checks line of sight to Earth along a descent with terrain out to 186 km and lunar curvature, and searches for fallback landing sites reachable from the exact state at each outage. It then plans a rover traverse from the touchdown point using A\* search, reporting Earth visibility, sunlight and battery along the route.

We apply it to a 1.2 km region of the Leibnitz Beta plateau (85.45° S, 31.55° E), selected from six NASA landing-site tiles because Earth remains above the horizon there at mean libration. In a 120 s terminal descent, Earth is lost at 100 s, and 11 fallback routes pass the prototype's checks from that moment. Later outages leave only one or two. The results are from a single scenario with illustrative vehicle values and simplified dynamics; they show the workflow rather than flight performance.

## 3. Introduction

*Keep the first paragraph on renewed lunar exploration and polar sites. Replace the rest with:*

A lander cannot be steered from Earth during its final descent. The round-trip light time is about 2.6 seconds, and terminal descent happens too quickly for ground controllers to intervene, so the vehicle must fly it autonomously regardless. What the communication link provides is oversight: telemetry for controllers, and a route for decisions such as a go/no-go call or a change of target when time allows.

Near the lunar south pole that link is not guaranteed. Earth sits low in the sky, moves with libration, and can be hidden by nearby terrain. A lander descending behind high ground can lose contact at the point when an unexpected problem would most need a decision.

Echo-Path explores one response: identify these outages before flight, and prepare vetted alternatives for each one, so that the vehicle already holds an answer if it needs one and the link is gone. It is a pre-flight planning tool. It does not run on a vehicle, and it does not attempt to replace onboard hazard detection.

The same terrain and line-of-sight tools extend to surface operations after landing, so Echo-Path also plans a rover traverse from the touchdown point, reporting where the rover would lose Earth contact or sunlight and how its battery would respond.

Our site survey (§8.1) shows how much these questions depend on location: at mean libration, Earth is at or very near the horizon from the four sites closest to the pole, but about 3.6° above it from Leibnitz Beta and Malapert.

*Remove these claims from the current paper, because no source supports them:*
- *"state-of-the-art onboard autonomous systems lack the computational bandwidth..."*
- *ground controllers "issue trajectory corrections" during blind descent*
- *"significantly increasing mission survivability"*

## 4. Related Work

**Hazard detection and avoidance.** NASA's Autonomous Landing and Hazard Avoidance Technology (ALHAT) project developed descent and landing guidance, navigation and control technology for the Moon, including onboard hazard detection [2]. Echo-Path works before flight, from existing maps, and complements such onboard systems rather than replacing them.

**Powered descent guidance.** Convex optimization can compute fuel-optimal powered descent trajectories [3] and minimum-landing-error trajectories when a target can't be reached [4]. Echo-Path uses a much simpler polynomial evaluator; these methods are natural replacements for it (§9).

**Polar topography and illumination.** LOLA [1] has produced high-resolution elevation models of the south polar region [5, 6]. Illumination at the poles is commonly computed from horizon elevations derived from such models, because distant terrain controls the low-angle light [7]. Echo-Path's distant-terrain check follows the same idea at a coarser level, for both sunlight and Earth visibility.

**Graph search.** The rover planner uses A\* [8].

*Remove the claims about what "traditional ALHAT-derived architectures" and "existing contingency architectures" assume, and that convex methods "require significant onboard computational resources". The team has no source for them. If you want a gap statement, cite a specific paper for it.*

## 5. Methodology

### 5.1 Terrain data

The default region is a 240 × 240 pixel crop (1.2 km square) of NASA GSFC's 5 m/pixel LOLA landing-site product for Site 20 [5], in south polar stereographic metres. Elevation is read at native resolution. Coordinates are local metres (x east, y north in the grid). Terrain beyond the crop comes from two coarser layers: the 16 km site tile averaged to 40 m/pixel, and the 80–90° S mosaic [6] reduced to 640 m/pixel. Together the files take about 2 MB.

### 5.2 Landing hazard

Slope is computed from central differences of elevation. Roughness is the RMS departure from a plane fitted over a neighbourhood matching the lander footprint (30 m by default). The hazard score is:

$H = \mathrm{clip}(0.65\,S/S_{max} + 0.35\,R/R_{max},\ 0,\ 1)$

with $S_{max} = 12°$ and $R_{max} = 1.5$ m. A cell is eligible only if its whole neighbourhood is known and within both limits; all other cells receive $H = 1$. When sunlight is required, it acts as a pass/fail filter rather than a weighted term.

### 5.3 Line of sight

A ray from each point toward a target azimuth and elevation is marched across the terrain, and any terrain above the ray blocks it. Within the crop the surface is treated as locally flat, at half-cell steps. Beyond it the ray crosses the coarser layers, using each only outside finer data and lowering distant ground by $d^2/2R$ to allow for lunar curvature. An elevation at or below 0° counts as blocked. Each sample is reported as clear, blocked or unknown.

The positions the Sun and Earth can take are computed from a Moon-fixed geometry using published extremes: libration of about ±6.7° in latitude and ±7.9° in longitude, and a solar latitude within ±1.54°. Directions are held fixed during a run; this is not a time-resolved ephemeris.

### 5.4 Descent model

The descent is a cubic position polynomial from the initial position and velocity to a stationary touchdown, with velocity and acceleration derived analytically. The required thrust acceleration is $|\mathbf{a} - \mathbf{g}|$ with $g = 1.62$ m/s², and mass follows:

$\frac{dm}{dt} = -\frac{\|T(t)\|}{I_{sp} g_0} \quad\Rightarrow\quad m(t) = m(0)\exp\left(-\int \frac{|\mathbf{a}-\mathbf{g}|}{I_{sp} g_0}\,dt\right)$

Routes are sampled at most 0.5 s and half a cell apart, and rejected if they leave known terrain, hit terrain, drop below dry mass, exceed maximum thrust or require downward thrust. This evaluates a commanded trajectory; it does not simulate a controller. The checks are sampled and are not a continuous proof of clearance.

### 5.5 Fallback selection

From the exact position, velocity, mass and remaining time at an outage, eligible cells are pre-scored by $H + 0.25\,d/L$ (distance $d$, map size $L$). Up to 16 cells at least 4 grid cells apart are chosen, always including the nearest. Each is tried at 0.8, 1.0 and 1.25 times the remaining time (at least 4 s). Feasible routes are ranked by:

$J = H + 0.4\,\frac{m_{used}}{m_{available}}$

where $m_{available}$ is the propellant remaining at the outage. This is a bounded heuristic search: it gives no guarantee of optimality, and finding no route does not prove none exists.

### 5.6 Rover traverse

Each cell receives a cost:

$c = 1 + 2\,S/S_{r} + R/R_{r} + p \cdot \mathrm{shadow}$

with rover limits $S_r = 20°$ and $R_r = 1$ m and $p = 1$. Cells beyond a limit are impassable. An 8-connected A\* search [8] finds the cheapest route, using straight-line distance as an admissible heuristic because every cell costs at least 1. Grid zig-zags are then removed, taking a straight shortcut only where it costs no more than the section it replaces.

The route is then driven in simulation. Speed falls with slope, $v = v_0 \max(0.3,\ 1 - S/S_r)$. Earth visibility and sunlight are ray-cast at each point, and the battery is integrated step by step with charge above full lost, stopping the rover if it empties. Default rover values (0.5 m/s, 600 Wh, 150 W driving, 40 W idle, 200 W solar) are illustrative.

## 6. System Architecture

Echo-Path keeps computation separate from presentation. The engine is a set of Python modules, one per concern:

- **`terrain`**: DEM loading, hazard maps and surrounding terrain layers.
- **`comms`**: line of sight and shadow raycasting.
- **`astro`**: Sun and Earth limits for a site.
- **`trajectory`**: descent model and feasibility checks.
- **`routing`**: fallback candidate search and ranking.
- **`rover`**: A\* route, smoothing and timed drive.
- **`evaluation`**: the results in §8.

Two front ends use this engine: a Streamlit dashboard for analysis, and a 3D web application reached through a small HTTP API. Because the modules communicate through plain data, one can be improved without rewriting the others, though changing what they exchange would still need changes on both sides.

*Remove the abstract interface names (`ITerrainProvider` etc.) and the "zero modifications" claim. Neither exists in the code.*

## 7. Implementation

| Component | Tools | Role |
|---|---|---|
| Engine | Python, NumPy, SciPy | Hazard maps, ray marching, descent model, rover |
| Geospatial I/O | Rasterio | Reading LOLA GeoTIFFs |
| API | FastAPI | Serves the engine to the web application |
| 3D application | React, TypeScript, Vite, Three.js | Interactive lander and rover scene |
| Dashboard | Streamlit, Plotly | Analysis and data export |
| Verification | unittest, GitHub Actions, Docker | 69 automated tests and a container check on every change |

A live demonstration is available at https://nasa-gitcantcommit.onrender.com/.

## 8. Evaluation

The results below are from one site and one scenario, with illustrative vehicle values: 700 kg dry mass, 300 kg propellant, 5000 N maximum thrust, 310 s specific impulse, and a 120 s descent from 350 m. Earth is at its mean position.

### 8.1 Site selection

At mean libration, Earth's elevation at the centre of each NASA landing-site tile is:

| Site | Latitude | Earth elevation |
|---|---|---:|
| Shackleton rim (Site 04) | 89.77° S | −0.5° |
| Connecting ridge (Site 01) | 89.46° S | −0.7° |
| Peak near Shackleton (Site 07) | 88.81° S | −0.9° |
| de Gerlache rim (Site 11) | 88.68° S | +0.2° |
| Malapert massif (Site 23) | 85.99° S | +3.7° |
| Leibnitz Beta plateau (Site 20) | 85.43° S | +3.6° |

Windows on the two sites with Earth clearly above the horizon were then scanned for a flyable default descent onto eligible ground. The chosen window at 85.45° S, 31.55° E has 81% landing-eligible area. There, Earth's elevation ranges from about −3.4° to +10.6° and the Sun peaks at about 6.1°.

### 8.2 Communication dropouts and fallback coverage

Earth is visible for most of the descent, then blocked from 100 s to touchdown (6 of 31 samples).

| Outage time (s) | Feasible fallbacks | With H < 0.25 |
|---:|---:|---:|
| 100 | 11 | 10 |
| 104 | 2 | 1 |
| 108 | 1 | 0 |
| 112 | 1 | 1 |
| 116 | 1 | 0 |

Having at least three fallbacks with H < 0.25 held for 1 of these 5 dropouts. Options fall quickly because less time remains to divert. An outage this late leaves little room; dropouts earlier in a descent would likely leave more, and windows exist where they occur earlier, though the one we examined (from 80 s) had far less eligible ground.

*Replace the paper's claim of "at least 3 ranked... fallback landing targets" at "any dropout point" with this measured result.*

### 8.3 Scenario comparison

| Metric | Nominal Flight | Unmitigated Outage | Echo-Path Fallback |
|---|---:|---:|---:|
| Landing hazard score (H) | 0.40 | 1.00 | 0.02 |
| Fuel margin remaining (%) | 79.0 | 79.0 | 75.7 |
| Touchdown slope (deg) | 6.8 | 12.1 | 0.0 |

**The "Unmitigated Outage" column is a constructed scenario.** To represent a target that ground control would have redirected away from, the target is moved to the nearest cell that fails the surface limits and can still be flown to. Its H of 1.00 reflects failing the limit by definition (12.1° against 12°), so it shouldn't be read as a measure of how dangerous that landing would be. The fallback's benefit is a much flatter site for about 3 percentage points of fuel margin. A single constructed case doesn't show a statistical improvement.

### 8.4 Rover traverse

From a point east of the map's centre (896 m, 598 m) to a goal in the north-west (180 m, 1020 m), with the Sun at 90° azimuth and 4.9° elevation, at the illustrative rover speed:

| Metric | A\* route | Straight line |
|---|---:|---:|
| Distance | 836 m (5 legs) | 829 m |
| Duration | 38.6 min | 40.6 min |
| Time with Earth blocked | 44% | 48% |
| Time in shadow | 24% | 22% |
| Battery at end | 96% | 96% |

The A\* route is slightly longer but about 2 minutes quicker, because it avoids steeper ground where the rover slows down. It doesn't reduce shadow here. The plateau is also gentle enough that almost no cells exceed the rover's limits, so this site doesn't test the planner's obstacle avoidance; automated tests check that separately on constructed terrain.

### 8.5 Checks on the method

- **Slope.** Computed slope matches NASA's published slope map for the same window to within 0.01° over 55,696 cells. This shows the engine reproduces the published product, but it isn't an independent accuracy check, since both use finite differences on the same grid.
- **Distant terrain.** Line of sight using the coarse layers was compared with the best available data (5 m tile, then 80 m mosaic) over 3,840 ray checks, from the ground and from 350 m, across 30 directions. They disagreed on 0.16% of checks, against 2.5% with no surrounding terrain. The effect is larger near the pole: at the Site 04 crop, a Sun in the west at 2° lights 33% of sampled spots using the crop alone and 3% using the full tile.

### 8.6 Reproducing these results

From `NASA Project/`:

```powershell
python -m echo_path.evaluation --dem data/lola_site20_r1560_c1320.tif --surround data/lola_site20_surround_40m.tif --surround data/lola_south_pole_surround_640m.tif --reference-slope data/lola_site20_r1560_c1320_slope.tif
python -m echo_path.rover --dem data/lola_site20_r1560_c1320.tif --surround data/lola_site20_surround_40m.tif --surround data/lola_south_pole_surround_640m.tif --goal 180 1020
```

## 9. Limitations and Future Work

**Limitations.**
- The Sun and Earth are fixed during a run, and relay satellites aren't modelled.
- Communication means geometric line of sight, with no link budget or antenna pointing.
- At 5 m/pixel, boulders and small craters aren't resolved, and DEM uncertainty isn't carried through the analysis.
- The lander is a point mass following a polynomial over a short terminal phase, with no attitude, throttle limits, engine lag or navigation error.
- Lander fallbacks come from a bounded search.
- Rover power doesn't depend on slope or Sun angle.
- Vehicle and rover values are illustrative.
- Results come from one site and one scenario.

**Future work.**
- Time-resolved Earth and Sun positions from an ephemeris, and relay satellites.
- Uncertainty margins on terrain, clearance and line of sight, building on published LOLA error estimates [5].
- Constrained powered-descent guidance [3, 4] in place of the polynomial evaluator, with a full descent from higher altitude.
- Evaluation across many sites, windows and outage times, to replace the single constructed comparison.
- A slope- and Sun-dependent rover power model.

*Remove the deep reinforcement learning, Mars and flight-processor (RAD750) items unless the team plans to pursue them. They're far from the current work and invite questions the project can't answer yet.*

## 10. Conclusion

Echo-Path connects lunar terrain, line of sight and contingency planning in one working tool. Using real LOLA data at the Leibnitz Beta plateau, it identifies where a descending lander loses sight of Earth, finds fallback sites from the exact outage state, and plans a rover's traverse with comms, sunlight and power along the way. Its site survey and distant-terrain checks show how strongly these questions depend on location and on terrain well beyond the landing area. Its fallback coverage shrinks quickly late in a descent, which suggests that outage timing matters as much as the site itself. The simplified dynamics and single scenario mean these results demonstrate an approach rather than flight performance; the priorities for further work are time-resolved Sun and Earth positions, uncertainty margins, and evaluation across many scenarios.

## 11. References

1. Smith, D. E., Zuber, M. T., Jackson, G. B., et al. (2010). The Lunar Orbiter Laser Altimeter Investigation on the Lunar Reconnaissance Orbiter Mission. *Space Science Reviews* 150, 209–241. doi:10.1007/s11214-009-9512-y
2. Epp, C. D., & Smith, T. B. (2007). The Autonomous Precision Landing and Hazard Detection and Avoidance Technology (ALHAT). NASA Technical Reports Server, 20060050771. *Cited by its NASA record because its publication venue couldn't be confirmed.*
3. Açıkmeşe, B., & Ploen, S. R. (2007). Convex Programming Approach to Powered Descent Guidance for Mars Landing. *Journal of Guidance, Control, and Dynamics* 30(5), 1353–1366. doi:10.2514/1.27553
4. Blackmore, L., Açıkmeşe, B., & Scharf, D. P. (2010). Minimum-Landing-Error Powered-Descent Guidance for Mars Landing Using Convex Optimization. *Journal of Guidance, Control, and Dynamics* 33(4), 1161–1171. doi:10.2514/1.47202
5. Barker, M. K., Mazarico, E., Neumann, G. A., et al. (2021). Improved LOLA elevation maps for south pole landing sites: Error estimates and their impact on illumination conditions. *Planetary and Space Science* 203, 105119. doi:10.1016/j.pss.2020.105119
6. Barker, M. K., et al. (2023). A New View of the Lunar South Pole from LOLA. *Planetary Science Journal* 4, 183. doi:10.3847/PSJ/acf3e1
7. Mazarico, E., Neumann, G. A., Smith, D. E., Zuber, M. T., & Torrence, M. H. (2011). Illumination conditions of the lunar polar regions using LOLA topography. *Icarus* 211(2), 1066–1081. doi:10.1016/j.icarus.2010.10.030
8. Hart, P. E., Nilsson, N. J., & Raphael, B. (1968). A Formal Basis for the Heuristic Determination of Minimum Cost Paths. *IEEE Transactions on Systems Science and Cybernetics* 4(2), 100–107. doi:10.1109/TSSC.1968.300136

*Before submitting, check each reference's full author list against the publisher's page. The libration and solar-latitude values in §5.3 are standard figures that should also get a citation, such as an astronomy reference the team trusts.*
