"""Echo-Path HTTP API for the 3D web app.

Run from "NASA Project":  python -m uvicorn api.main:app --reload
Grids are flattened row-major with row 0 at the south edge; x = col*dx, y = row*dy, in metres.
If the web app has been built (web/dist, or the folder in ECHO_PATH_WEB_DIST), it is served from
the same address, so one process is the whole deployable site.
"""
import os
from dataclasses import asdict, replace
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Optional
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from echo_path.terrain import synthetic, load_dem, load_surround, hazards
from echo_path.astro import site_of, sky_limits
from echo_path.comms import visibility
from echo_path.trajectory import Vehicle, trajectory
from echo_path.routing import plan_fallbacks
from echo_path.rover import Rover, traversability, plan_rover

DATA = Path(__file__).resolve().parents[1] / 'data'
WEB_DIST = Path(os.environ.get('ECHO_PATH_WEB_DIST', Path(__file__).resolve().parents[2] / 'web' / 'dist'))
POLAR_LAYER = 'lola_south_pole_surround_640m.tif'
TERRAINS = {
    'lola_site20': {'label': 'LOLA Leibnitz Beta plateau, PGDA Site20 (85.45°S, 31.55°E)',
                    'dem': 'lola_site20_r1560_c1320.tif', 'surround': ['lola_site20_surround_40m.tif', POLAR_LAYER],
                    'goal_pct': (15., 85.)},
    'lola_site04': {'label': 'LOLA near the pole, PGDA Site04 (89.48°S, 156.05°W), Earth low or hidden',
                    'dem': 'lola_site04_r2960_c400.tif', 'surround': ['lola_site04_surround_40m.tif', POLAR_LAYER],
                    'goal_pct': (15., 85.)},
    'synthetic': {'label': 'Synthetic ridge and landing basin (no real sky)', 'goal_pct': (90., 90.)},
}
SYNTHETIC_SKY = {'earth_az': 270., 'earth_el': 3., 'earth_el_min': -5., 'earth_el_max': 30.,
                 'sun_az': 90., 'sun_el': 5., 'sun_el_min': -5., 'sun_el_max': 30., 'lat': None, 'lon': None}
SUN_DEFAULT_FRACTION = .8   # a typical high Sun for the site, below its absolute peak
SAMPLES = 31

app = FastAPI(title='Echo-Path API')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
                   allow_methods=['*'], allow_headers=['*'])
app.add_middleware(GZipMiddleware, minimum_size=1024)   # a mission response is about 1 MB of JSON


def _terrain(terrain_id):
    if terrain_id not in TERRAINS:
        raise HTTPException(404, f'Unknown terrain {terrain_id!r}.')
    return _load(terrain_id)


@lru_cache(maxsize=None)
def _load(terrain_id):
    spec = TERRAINS[terrain_id]
    if 'dem' not in spec:
        return synthetic()
    t = load_dem(str(DATA/spec['dem']), size=240)
    t.surroundings = [load_surround(str(DATA/name), t) for name in spec['surround']]
    return t


@lru_cache(maxsize=None)
def _sky(terrain_id):
    """What the app may offer for this terrain: real Sun and Earth limits, defaults and how far horizons are known."""
    t = _load(terrain_id)
    goal = TERRAINS[terrain_id]['goal_pct']
    known = {'goal_xy': [goal[0]/100*t.width, goal[1]/100*t.height], 'horizon_km': 0.}
    if not t.surroundings:
        return {**SYNTHETIC_SKY, **known}
    lat, lon = site_of(t)
    limits = sky_limits(lat, lon)
    earth, sun = limits['earth'], limits['sun']
    # Distance from the crop centre to the nearest edge of the coarsest terrain layer.
    left, right, south, north = t.surroundings[-1].box
    cx, cy = t.width/2, t.height/2
    known['horizon_km'] = round(min(cx-left, right-cx, cy-south, north-cy)/1000)
    return {'earth_az': round(earth['mean_az'] % 360, 1), 'earth_el': round(earth['mean_el'], 1),
            'earth_el_min': round(earth['el_min'], 1), 'earth_el_max': round(earth['el_max'], 1),
            'sun_az': 90., 'sun_el': round(sun['el_max']*SUN_DEFAULT_FRACTION, 1),
            'sun_el_min': round(sun['el_min'], 1), 'sun_el_max': round(sun['el_max'], 1),
            'lat': round(lat, 4), 'lon': round(lon, 4), **known}


@lru_cache(maxsize=32)
def _hazards(terrain_id, slope, roughness, footprint):
    return hazards(_load(terrain_id), slope, roughness, footprint)


@lru_cache(maxsize=32)
def _rover_grid(terrain_id, rover, sun_az, sun_el):
    return traversability(_load(terrain_id), rover, sun_az, sun_el)


def _grid(a, digits):
    return np.round(np.nan_to_num(np.asarray(a, float), nan=-9999.), digits).ravel().tolist()


def _xyz(p, digits=2):
    return np.round(np.asarray(p, float), digits).tolist()


Percent = Annotated[float, Field(ge=0, le=100)]
Azimuth = Annotated[float, Field(ge=0, le=360)]
Elevation = Annotated[float, Field(ge=-90, le=90)]


class MissionRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    terrain: str = 'synthetic'
    slope: float = Field(12., gt=0, le=90)
    roughness: float = Field(1.5, gt=0)
    footprint: float = Field(30., gt=0)
    start_pct: tuple[Percent, Percent] = (15., 50.)
    target_pct: tuple[Percent, Percent] = (75., 50.)
    altitude: float = Field(350., ge=0)
    duration: float = Field(120., gt=0)
    velocity: tuple[float, float, float] = (4., 0., -3.)
    dry_mass: float = Field(700., gt=0)
    fuel: float = Field(300., ge=0)
    max_thrust: float = Field(5000., gt=0)
    isp: float = Field(310., gt=0)
    earth_az: Optional[Azimuth] = None   # None = this terrain's default sky
    earth_el: Optional[Elevation] = None
    outage_step: Optional[int] = Field(None, ge=0, lt=SAMPLES, description='Comms sample to fail; default is the first blocked one')


class RoverRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    terrain: str = 'synthetic'
    start: tuple[float, float]
    goal: tuple[float, float]
    earth_az: Optional[Azimuth] = None   # None = this terrain's default sky
    earth_el: Optional[Elevation] = None
    sun_az: Optional[Azimuth] = None     # left out = terrain default; an explicit null plans without the Sun
    sun_el: Optional[Elevation] = None
    max_slope: float = Field(20., gt=0, le=90)
    max_roughness: float = Field(1., gt=0)
    speed: float = Field(.5, gt=0)
    start_battery_pct: Percent = 100.


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.get('/api/terrains')
def terrains():
    out = []
    for key, spec in TERRAINS.items():
        t = _load(key)
        out.append({'id': key, 'label': spec['label'], 'rows': t.z.shape[0], 'cols': t.z.shape[1],
                    'dx': t.dx, 'dy': t.dy, 'width_m': t.width, 'height_m': t.height, 'sky': _sky(key)})
    return out


@app.post('/api/mission')
def mission(req: MissionRequest):
    t = _terrain(req.terrain)
    sky = _sky(req.terrain)
    earth_az = sky['earth_az'] if req.earth_az is None else req.earth_az
    earth_el = sky['earth_el'] if req.earth_el is None else req.earth_el
    h = _hazards(req.terrain, req.slope, req.roughness, req.footprint)
    sx, sy = req.start_pct[0]/100*t.width, req.start_pct[1]/100*t.height
    tx, ty = req.target_pct[0]/100*t.width, req.target_pct[1]/100*t.height
    start = [sx, sy, float(t.sample(sx, sy))+req.altitude]
    end = [tx, ty, float(t.sample(tx, ty))]
    if not np.isfinite(start+end).all():
        raise HTTPException(422, 'Start or target lies on missing DEM data.')
    vehicle = Vehicle(req.dry_mass, req.fuel, req.max_thrust, req.isp)
    try:
        nominal = trajectory(t, start, req.velocity, end, req.duration, req.dry_mass+req.fuel, vehicle)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    samples = np.unique(np.linspace(0, len(nominal['t'])-1, SAMPLES).astype(int))
    comms = visibility(t, nominal['position'][samples], earth_az, earth_el)
    blocked = np.flatnonzero(comms == 0)
    step = req.outage_step if req.outage_step is not None else (int(blocked[0]) if len(blocked) else SAMPLES//2)
    step = min(step, len(samples)-1)
    index = int(samples[step])
    options, diagnostics = ([], {'tested': 0, 'rejected': {}})
    if nominal['feasible']:
        options, diagnostics = plan_fallbacks(t, h, nominal, index, vehicle)
    shown = np.unique(np.linspace(0, len(nominal['t'])-1, 200).astype(int))
    fallbacks = []
    for rank, o in enumerate(options, 1):
        route = o['route']
        keep = np.unique(np.linspace(0, len(route['t'])-1, 120).astype(int))
        fallbacks.append({'rank': rank, **{k: o[k] for k in ('x_m', 'y_m', 'hazard', 'slope_deg', 'roughness_m',
                                                             'fuel_used_kg', 'fuel_remaining_kg', 'duration_s', 'score')},
                          'touchdown': _xyz(route['position'][-1]), 'path': _xyz(route['position'][keep]),
                          'time_s': _xyz(route['t'][keep])})
    return {
        'terrain': {'id': req.terrain, 'source': t.source, 'rows': t.z.shape[0], 'cols': t.z.shape[1], 'dx': t.dx, 'dy': t.dy,
                    'z_min': float(np.nanmin(t.z)), 'z_max': float(np.nanmax(t.z)), 'nodata': -9999.,
                    'z': _grid(t.z, 2), 'hazard': _grid(h['hazard'], 3), 'slope': _grid(h['slope'], 2), 'sky': sky},
        'eligible_pct': float(100*h['safe'].mean()),
        'earth': {'azimuth_deg': earth_az, 'elevation_deg': earth_el},
        'nominal': {'feasible': nominal['feasible'], 'reasons': nominal['reasons'], 'fuel_used_kg': nominal['fuel_used'],
                    'peak_thrust_n': nominal['peak_thrust'], 'path': _xyz(nominal['position'][shown]),
                    'time_s': _xyz(nominal['t'][shown]), 'touchdown': _xyz(nominal['position'][-1])},
        'comms': [{'step': i, 'time_s': float(nominal['t'][s]), 'position': _xyz(nominal['position'][s]),
                   'state': int(c)} for i, (s, c) in enumerate(zip(samples, comms))],
        'outage': {'step': step, 'time_s': float(nominal['t'][index]), 'position': _xyz(nominal['position'][index])},
        'fallbacks': fallbacks,
        'diagnostics': diagnostics,
    }


@app.post('/api/rover')
def rover(req: RoverRequest):
    t = _terrain(req.terrain)
    sky = _sky(req.terrain)
    earth_az = sky['earth_az'] if req.earth_az is None else req.earth_az
    earth_el = sky['earth_el'] if req.earth_el is None else req.earth_el
    spec = replace(Rover(), max_slope=req.max_slope, max_roughness=req.max_roughness, speed=req.speed,
                   start_battery_pct=req.start_battery_pct)
    sun_az = req.sun_az if 'sun_az' in req.model_fields_set else sky['sun_az']
    sun_el = req.sun_el if 'sun_el' in req.model_fields_set else sky['sun_el']
    # The Sun model needs both angles; with either one missing the rover plans without it.
    if None in (sun_az, sun_el):
        sun_az = sun_el = None
    grid = _rover_grid(req.terrain, spec, sun_az, sun_el)
    result = plan_rover(t, req.start, req.goal, spec, earth_az, earth_el, sun_az, sun_el, grid=grid)
    result['rover'] = asdict(spec)
    result['earth'] = {'azimuth_deg': earth_az, 'elevation_deg': earth_el}
    result['sun'] = None if sun_el is None else {'azimuth_deg': sun_az, 'elevation_deg': sun_el}
    return result


def mount_web(target, folder):
    """Serve the built web app at the site root. Registered last so /api routes take priority."""
    if Path(folder).is_dir():
        target.mount('/', StaticFiles(directory=folder, html=True), name='web')


mount_web(app, WEB_DIST)
