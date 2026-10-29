[[NASA Space Apps Challenge 2026 - Plan]]


---
project: Echo-Path
type: Academic Paper Draft / System Architecture
author: Christian T. Rocero
institution: Batangas State University - Alangilan
program: 2nd Year BS Computer Science
status: Active Development
tags:
  - aerospace
  - lunar-landing
  - pathfinding
  - simulation
  - capstone
  - space-apps
---

# 🚀 ECHO-PATH: PRE-FLIGHT FALLBACK TRAJECTORY PLANNING FOR LUNAR DESCENT UNDER TELEMETRY OUTAGE
**A Modular Architecture for Autonomous Contingency Routing in Unconstrained Lunar Terrain**

---

## 1. Proposed Project Titles
- **Option A (Technical / Operational Focus):** Predictive Fallback Routing for Autonomous Lunar Descent Under Line-of-Sight Telemetry Outages.
- **Option B (System / Architectural Focus):** Echo-Path: A Modular Pre-Flight Planning Framework for Lunar Landing Contingency and Hazard Mitigation.
- **Option C (Problem / Capability Focus):** Mitigating 'Blind Descent' Vulnerabilities in Lunar Landers via Precomputed Fallback Trajectories and Terrain Hazard Mapping.

## 2. Abstract
Safe lunar landing requires highly accurate navigation and real-time hazard avoidance during the powered descent phase. However, existing mission architectures encounter severe operational vulnerabilities when line-of-sight communication with Earth or orbital relay assets is lost—a condition known as 'blind descent.' During telemetry outages, landers are unable to receive dynamic re-evaluation commands from ground control and must rely strictly on pre-loaded nominal flight plans or onboard inertial guidance, exposing the vehicle to unmitigated surface hazards. 

This paper presents **Echo-Path (v1)**, a pre-flight mission planning tool designed to map lunar terrain hazards, simulate geometric communication dropout corridors, and compute optimized fallback landing trajectories. By parsing high-resolution Lunar Reconnaissance Orbiter Laser Altimeter (LOLA) Digital Elevation Models (DEMs), the system derives surface slope, roughness, and illumination constraints to build comprehensive hazard matrices. A point-mass kinematic solver simulates nominal descent trajectories while a geometric line-of-sight model identifies terrain and horizon occlusion points. At each dropout location, a heuristic search algorithm evaluates reachable safe landing zones and precomputes candidate fallback trajectories subject to residual fuel and thrust limits. Built behind modular, decoupled interfaces, Echo-Path ensures seamless future extensions to multi-body environments, live ephemeris tracking, and real-time onboard execution, establishing a robust framework for autonomous lunar landing contingency management.

## 3. Introduction
The renewal of global interest in lunar surface exploration—marked by NASA's Artemis program, international scientific endeavors, and commercial payload delivery initiatives—has shifted landing site selection from benign, equatorial maria to complex, high-interest polar regions. While regions such as the Lunar South Pole possess rich scientific resources and permanently shadowed cold traps containing water ice, their extreme topography presents severe operational risks during the Powered Descent Initiation (PDI) and Terminal Descent phases.

A primary hazard facing modern lunar landers is the temporary or catastrophic loss of communications telemetry. Direct-to-Earth (DTE) radio links and lunar relay satellite connections are frequently disrupted by local topography (e.g., deep crater rims, mountain occlusions) or planetary geometry (e.g., crossing the lunar limb). During these 'blind descent' corridors, ground controllers cannot monitor vehicle health, override erroneous sensor inputs, or issue trajectory corrections. Concurrently, state-of-the-art onboard autonomous systems lack the computational bandwidth to perform real-time, global re-evaluation of candidate landing zones while executing high-g deceleration maneuvers.

To solve this operational vulnerability, this work introduces **Echo-Path (v1)**: a pre-flight mission planning and contingency routing tool. Echo-Path pre-identifies potential communication dropout zones along a nominal landing corridor and precomputes ranked, dynamically feasible fallback trajectories to alternate safe landing sites. Should communication fail mid-descent, the onboard guidance computer transitions to a validated contingency path rather than blindly executing a compromised flight plan, significantly increasing mission survivability.

## 4. Related Work
Autonomous planetary landing research spans several decades, progressing from open-loop Apollo guidance to advanced closed-loop Autonomous Landing and Hazard Avoidance Technology (ALHAT). Historical and current approaches generally fall into three categories:

- **Terrain-Relative Navigation & Hazard Avoidance:** Programs such as NASA's ALHAT established the foundation for real-time hazard detection using LIDAR and Optical Terrain-Relative Navigation (TRN). TRN matches surface optical images or altimetry grids against onboard reference maps to correct inertial drift. However, traditional ALHAT-derived architectures focus on local divert maneuvers during the final tens of meters and assume continuous state estimation without addressing systemic communication blackouts occurring earlier in the descent trajectory.
- **G-Fold & Optimal Powered Descent Guidance:** Precomputed guidance tables and convex optimization techniques (e.g., lossless convexification of powered descent guidance) allow landers to compute fuel-optimal trajectories. While highly effective, these algorithms require significant onboard computational resources and pre-suppose a fixed, uncompromised destination target. When communication outages disrupt telemetry validation, executing a single pre-calculated trajectory can lead to catastrophic landing failure if local surface conditions diverge from expectation.
- **Contingency and Fallback Frameworks:** Existing contingency architectures typically treat communication loss as a trigger for immediate abort sequences (e.g., solid motor staging or orbit insertion). Echo-Path bridges the gap between rigid mission aborts and local optical diverts by providing a global, precomputed fallback topology mapping communication outage locations directly to reachable safe landing sites.

## 5. Methodology
The Echo-Path pipeline comprises five core analytical stages designed to process raw lunar telemetry into actionable contingency trajectories.

### 5.1 Terrain Data Pipeline
The system parses high-resolution Digital Elevation Models (DEMs) acquired by the Lunar Reconnaissance Orbiter Laser Altimeter (LOLA) and the SELENE (Kaguya) Terrain Camera. The terrain pipeline extracts heightfield matrices $Z(x, y)$, normalizes spatial resolutions, and converts geographic coordinates (latitude/longitude) into a local East-North-Up (ENU) Cartesian frame centered at the nominal landing site.

### 5.2 Hazard Scoring Model
Surface safety is quantified using a multi-criteria hazard metric $H(x, y) \in [0, 1]$, where $0$ represents an ideal landing surface and $1$ represents an unviable, fatal hazard. The hazard score combines three primary physical indicators:
- **Local Slope ($S$):** Derived from spatial elevation gradients using 3x3 Sobel operators, penalizing slopes exceeding vehicle tip-over limits (typically > 12-15 degrees).
- **Surface Roughness ($R$):** Quantified using terrain variance or detrended RMS height variation across a localized window matching the lander footprint, identifying boulders and micro-craters.
- **Illumination Constraints ($I$):** Modeled using ray-casting based on low solar elevation angles typical of lunar polar regions, flagging deep shadows that degrade optical TRN sensors.

The composite hazard score is defined as a weighted linear combination: 
$H = w_s S_{norm} + w_r R_{norm} + w_i I_{norm}$
subject to thresholding where $S > S_{max}$ results in an absolute hazard score of $1.0$.

### 5.3 Line-of-Sight and Communication Dropout Modeling
Communication availability along the descent path is modeled geometrically. Line-of-sight (LOS) vectors are cast from points along the trajectory toward tracking assets (Direct-to-Earth ground stations or Lunar Relay Satellites). A dropout condition is registered whenever a ray vector intersects the lunar DEM (local terrain masking) or passes below the planetary horizon (lunar-limb occlusion). This outputs a binary communication state vector $C(t) \in \{0, 1\}$ mapped along the flight profile.

### 5.4 Point-Mass Descent Trajectory Simulation
Vehicle dynamics during Powered Descent Initiation (PDI) are governed by a 3-DOF point-mass differential equation system:

$$ \frac{d}{dt} \begin{bmatrix} \mathbf{r}(t) \\ \mathbf{v}(t) \end{bmatrix} = \begin{bmatrix} \mathbf{v}(t) \\ \mathbf{g}(\mathbf{r}) + \frac{T(t)}{m(t)} \mathbf{u}(t) \end{bmatrix} $$

$$ \frac{dm}{dt} = -\frac{||T(t)||}{I_{sp} g_0} $$

where $\mathbf{r}(t)$ and $\mathbf{v}(t)$ are position and velocity vectors, $\mathbf{g}(\mathbf{r})$ is local lunar gravitational acceleration, $T(t)$ is thrust magnitude, $\mathbf{u}(t)$ is the unit direction vector, $m(t)$ is vehicle mass, and $I_{sp}$ is specific impulse. A baseline Gravity Turn or Polynomial Guidance law drives the nominal flight path from orbital de-boost to final touchdown.

### 5.5 Fallback Route Selection Algorithm
For each timestep where $C(t) = 0$ (communication blackout), the algorithm executes a fallback query:
1. **Reachability Envelope:** Computes a 3D reachable footprint based on remaining delta-v budget $\Delta v_{rem} = I_{sp} g_0 \ln(m_{current} / m_{dry})$ and thrust-to-weight limits.
2. **Hazard Filtering:** Filters all spatial nodes within the reachable footprint where hazard score $H(x, y) < H_{threshold}$.
3. **Trajectory Optimization & Ranking:** Ranks candidate sites using a heuristic cost function $J = w_1 H + w_2 \Delta v_{cost} + w_3 D_{drift}$, balancing site safety, fuel consumption, and deviation from the nominal mission profile.

## 6. System Architecture
Echo-Path is designed with a strict modular architecture. By isolating core analytical engines behind abstract base classes and stable interfaces, the framework allows individual subsystems to be upgraded or swapped without rearchitecting the entire system.

> **ARCHITECTURAL DESIGN PRINCIPLE:** The v1 architecture enforces strict decoupling between data loading, physical simulation, and routing logic. This design pattern ensures that replacing static geometric comms with complex orbital ephemeris, or replacing a heuristic fallback router with a deep reinforcement learning model, requires zero modifications to the core data pipeline.

- **Terrain Module (`ITerrainProvider`):** Abstracts DEM loading and coordinate transformations (e.g., LOLA GeoTIFF loader).
- **Hazard Module (`IHazardEvaluator`):** Computes composite safety matrices from elevation rasters.
- **Comms Module (`ICommsModel`):** Evaluates line-of-sight and returns communication availability vectors.
- **Trajectory Engine (`ITrajectorySimulator`):** Propagates point-mass dynamics and solves guidance equations.
- **Fallback Router (`IFallbackPlanner`):** Identifies reachable safe sites and generates ranked contingency routes.
- **User Interface / Visualization:** Exposes a lightweight visual dashboard / Jupyter interface for mission analysts.

## 7. Implementation Details
Echo-Path (v1) is implemented in Python 3.10+, leveraging scientific computing and geospatial libraries:

| Component | Library / Tool | Functionality |
| :--- | :--- | :--- |
| **Geospatial I/O** | `RasterIO` / `GDAL` | Parsing LOLA DEM GeoTIFFs, coordinate transformation |
| **Hazard Engine** | `NumPy` / `SciPy` | Sobel gradient calculation, RMS roughness, matrix scoring |
| **Trajectory Solver** | `SciPy` (`solve_ivp`) | Numerical integration of 3-DOF kinematic equations |
| **Fallback Planner** | Custom $A^*$ / `SciPy` | Heuristic graph search over reachable low-hazard nodes |
| **Dashboard / UI** | `Streamlit` / `Plotly` | Interactive 3D visualization and parameter control |

## 8. Evaluation and Expected Results
System validation focuses on verifying pipeline correctness, analytical consistency, and operational utility using simulated mission scenarios:
- **Hazard Map Generation:** Verification of successful GeoTIFF parsing and generation of normalized 2D/3D hazard maps for candidate polar landing sites.
- **Dropout Identification:** Identification of explicit communication blackout zones along a simulated 120-second final descent trajectory, correlating blackout windows with local crater rim occlusion.
- **Fallback Path Generation:** Demonstration that for any dropout point $t_{outage}$, the system outputs at least 3 ranked, dynamically reachable fallback landing targets with $H < 0.25$.
- **Metrics & Validation Framework:** Quantifying performance improvements compared to rigid, non-adaptive guidance execution under telemetry loss.

| Metric Parameter | Nominal Flight | Unmitigated Outage | Echo-Path Fallback |
| :--- | :--- | :--- | :--- |
| **Landing Hazard Score (H)** | [insert score] | [insert score - high] | [insert score - low] |
| **Fuel Margin Remaining (%)** | [insert %] | [insert %] | [insert %] |
| **Touchdown Slope (deg)** | [insert deg] | [insert deg - unsafe] | [insert deg - safe] |

## 9. Limitations and Future Work
While Echo-Path (v1) establishes a functional pre-flight routing framework, several architectural extension points are identified for future iterations:
- **Multi-Body Environment Expansion:** Adapting terrain and atmospheric density modules to support Martian descent dynamics (HiRISE/MOLA data).
- **Dynamic Ephemeris & Comms Modeling:** Transitioning from static geometric line-of-sight to dynamic, ephemeris-driven models incorporating real-time positions of relay satellite constellations and light-speed latency.
- **AI-Driven Fallback Planner:** Replacing heuristic graph search with Deep Reinforcement Learning (DRL) or neural network surrogates to compress precomputed routing lookup tables.
- **Web-Based Mission Interface:** Evolving the Python desktop environment into a cloud-native microservice architecture with WebGL/Three.js front-end visualization.
- **Onboard Real-Time Execution:** Optimizing routing algorithms to run on radiation-hardened flight processors (e.g., RAD750), transitioning Echo-Path from pre-flight planning to real-time onboard contingency execution.

## 10. Conclusion
The Echo-Path framework directly addresses the critical operational vulnerability of 'blind descent' during lunar landing operations. By fusing high-resolution LOLA elevation datasets, multi-criteria hazard scoring, geometric communication dropout modeling, and kinematic trajectory optimization, the system successfully precomputes dynamically feasible fallback routes to safe alternate sites. Its modular architectural design ensures seamless integration with future dynamic orbital models and onboard flight software. Echo-Path provides a foundational step toward fully autonomous, highly resilient planetary landing architectures capable of safely navigating the most challenging terrain in the solar system.

## 11. References
1. **NASA LRO / LOLA Technical Reports & Instrument Papers:** Technical documentation detailing instrument specs, spatial resolution, and processing pipelines (e.g., Smith et al., LOLA Science Team).
2. **NASA ALHAT Program Publications:** Publications detailing the Autonomous Landing and Hazard Avoidance Technology project, LIDAR hazard detection, and optical TRN algorithms.
3. **Planetary Landing Guidance Literature:** Foundational literature on powered descent guidance, convex optimization (G-Fold), and fuel-optimal landing algorithms (e.g., Acikmese, Ploen, Blackmore).
4. **Orbital Mechanics & Telemetry Handbooks:** Standard reference texts covering orbital mechanics, line-of-sight geometry, line-of-sight blackout analysis, and planetary ephemeris modeling (e.g., Vallado, Bate, Mueller & White).
5. **Motion Planning & Graph Search Algorithms:** Academic literature covering $A^*$, Dijkstra, and motion planning for autonomous vehicles operating in constrained environments.