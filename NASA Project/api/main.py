"""Echo-Path HTTP API for the 3D web app.

Run from "NASA Project":  python -m uvicorn api.main:app --reload
Grids are flattened row-major with row 0 at the south edge; x = col*dx, y = row*dy, in metres.
If the web app has been built (web/dist, or the folder in ECHO_PATH_WEB_DIST), it is served from
the same address, so one process is the whole deployable site.
"""
import gzip
import json
import os
from dataclasses import asdict, replace
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Optional
import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from echo_path.terrain import synthetic, random_moon, load_dem, load_surround, hazards
from echo_path.astro import grid_to_lat_lon, site_of, sky_limits
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
RANDOM_PREFIX = 'random-'   # 'random-<seed>' is a generated surface; any seed up to six digits
RANDOM_SEED_DIGITS = 6
SYNTHETIC_SKY = {'earth_az': 270., 'earth_el': 3., 'earth_el_min': -5., 'earth_el_max': 30.,
                 'sun_az': 90., 'sun_el': 5., 'sun_el_min': -5., 'sun_el_max': 30., 'lat': None, 'lon': None}
SUN_DEFAULT_FRACTION = .8   # a typical high Sun for the site, below its absolute peak
SAMPLES = 31
HORIZON_CELLS = 200         # the landscape drawn around the crop is thinned to about this many cells a side
SITE_COUNT = 5
SITE_CANDIDATES = 8
SITE_SPACING_FRACTION = .08 # recommended sites stay this fraction of the map apart, so they offer real choices
SITE_NO_VIEW_PENALTY = .1   # added to a site's score for each of Earth and Sun it can't see
SITE_STRANDED_PENALTY = .5  # added when a rover with default limits couldn't drive from the site to the goal
LANDER_ANTENNA_M = 3.

app = FastAPI(title='Echo-Path API')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
                   allow_methods=['*'], allow_headers=['*'])
app.add_middleware(GZipMiddleware, minimum_size=1024)   # a mission response is about 1 MB of JSON


def _random_seed(terrain_id):
    """The seed in a 'random-<seed>' terrain id, or None for any other id."""
    digits = terrain_id[len(RANDOM_PREFIX):] if terrain_id.startswith(RANDOM_PREFIX) else ''
    return int(digits) if digits.isdigit() and len(digits) <= RANDOM_SEED_DIGITS else None


def _terrain(terrain_id):
    if terrain_id not in TERRAINS and _random_seed(terrain_id) is None:
        raise HTTPException(404, f'Unknown terrain {terrain_id!r}.')
    return _load(terrain_id)


def _load(terrain_id):
    seed = _random_seed(terrain_id)
    return _random_surface(seed) if seed is not None else _load_site(terrain_id)


@lru_cache(maxsize=None)
def _load_site(terrain_id):
    spec = TERRAINS[terrain_id]
    if 'dem' not in spec:
        return synthetic()
    t = load_dem(str(DATA/spec['dem']), size=240)
    t.surroundings = [load_surround(str(DATA/name), t) for name in spec['surround']]
    return t


@lru_cache(maxsize=16)   # anyone can ask for any seed, so only recent surfaces are kept
def _random_surface(seed):
    return random_moon(seed)


@lru_cache(maxsize=64)
def _sky(terrain_id):
    """What the app may offer for this terrain: real Sun and Earth limits, defaults and how far horizons are known."""
    t = _load(terrain_id)
    if 'goal_xy' in t.metadata:
        goal_xy = list(t.metadata['goal_xy'])
    else:
        goal = TERRAINS[terrain_id]['goal_pct']
        goal_xy = [goal[0]/100*t.width, goal[1]/100*t.height]
    known = {'goal_xy': goal_xy, 'horizon_km': 0.}
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


@lru_cache(maxsize=16)
def _goal_area(terrain_id):
    """Cells a rover with default limits can drive between and the rover goal: one connected stretch of ground.

    Joined through edges only: the route search never cuts diagonally between two blocked cells, so a diagonal
    touch alone doesn't connect two areas.
    """
    from scipy.ndimage import label
    t = _load(terrain_id)
    open_ground = ~_rover_grid(terrain_id, Rover(), None, None)['blocked']
    parts, _ = label(open_ground)
    gx, gy = _sky(terrain_id)['goal_xy']
    row = int(np.clip(round(gy/t.dy), 0, t.z.shape[0]-1))
    col = int(np.clip(round(gx/t.dx), 0, t.z.shape[1]-1))
    return parts == parts[row, col] if parts[row, col] else np.zeros_like(open_ground)


def _grid(a, digits):
    return np.round(np.nan_to_num(np.asarray(a, float), nan=-9999.), digits).ravel().tolist()


def _xyz(p, digits=2):
    return np.round(np.asarray(p, float), digits).tolist()


def _route_json(route, points, terrain, earth_az, earth_el):
    """A flown route, thinned to about `points` samples, with what the navigation display shows."""
    keep = np.unique(np.linspace(0, len(route['t'])-1, points).astype(int))
    return {'path': _xyz(route['position'][keep]), 'time_s': _xyz(route['t'][keep]), 'velocity': _xyz(route['velocity'][keep]),
            'mass_kg': _xyz(route['mass'][keep], 1), 'thrust_n': _xyz(route['thrust'][keep], 0),
            'link': visibility(terrain, route['position'][keep], earth_az, earth_el).tolist()}


def _cell_report(terrain, hazard, x, y):
    """What the map says about the ground at a point."""
    row = int(np.clip(round(y/terrain.dy), 0, terrain.z.shape[0]-1))
    col = int(np.clip(round(x/terrain.dx), 0, terrain.z.shape[1]-1))
    roughness = float(hazard['roughness'][row, col])
    return {'x_m': float(x), 'y_m': float(y), 'z_m': float(terrain.z[row, col]), 'hazard': float(hazard['hazard'][row, col]),
            'slope_deg': float(hazard['slope'][row, col]), 'roughness_m': roughness if np.isfinite(roughness) else None,
            'eligible': bool(hazard['safe'][row, col])}


def _in_view(terrain, x, y, height, azimuth, elevation):
    """Whether a direction in the sky can be seen from `height` metres above the ground at a point."""
    z = float(terrain.sample(x, y))+height
    return int(visibility(terrain, np.array([[x, y, z]]), azimuth, elevation)[0]) == 1


def _lat_lon(terrain, x, y):
    if 'southwest_pixel_center' not in terrain.metadata:
        return None, None
    ox, oy = terrain.metadata['southwest_pixel_center']
    return grid_to_lat_lon(ox+x, oy+y)


def _resolved_sky(req, sky):
    earth_az = sky['earth_az'] if req.earth_az is None else req.earth_az
    earth_el = sky['earth_el'] if req.earth_el is None else req.earth_el
    sun_az = sky['sun_az'] if req.sun_az is None else req.sun_az
    sun_el = sky['sun_el'] if req.sun_el is None else req.sun_el
    return earth_az, earth_el, sun_az, sun_el


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
    target_xy: Optional[tuple[float, float]] = None   # overrides target_pct; metres on the local grid
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


class SkyRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    terrain: str = 'synthetic'
    earth_az: Optional[Azimuth] = None   # None = this terrain's default sky
    earth_el: Optional[Elevation] = None
    sun_az: Optional[Azimuth] = None
    sun_el: Optional[Elevation] = None


class PointRequest(SkyRequest):
    x: float
    y: float


class DivertRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    terrain: str = 'synthetic'
    position: tuple[float, float, float]
    velocity: tuple[float, float, float]
    mass: float = Field(gt=0)
    remaining_s: float = Field(gt=0)
    target: tuple[float, float]
    earth_az: Optional[Azimuth] = None   # None = this terrain's default sky
    earth_el: Optional[Elevation] = None


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


@lru_cache(maxsize=8)
def _terrain_payload(terrain_id, slope, roughness, footprint):
    """Grids only change with the terrain and limits, so they are encoded and compressed once."""
    t = _load(terrain_id)
    h = _hazards(terrain_id, slope, roughness, footprint)
    raw = json.dumps({'id': terrain_id, 'source': t.source, 'rows': t.z.shape[0], 'cols': t.z.shape[1], 'dx': t.dx, 'dy': t.dy,
                      'z_min': float(np.nanmin(t.z)), 'z_max': float(np.nanmax(t.z)), 'nodata': -9999.,
                      'z': _grid(t.z, 2), 'hazard': _grid(h['hazard'], 3), 'slope': _grid(h['slope'], 2),
                      'roughness': _grid(h['roughness'], 2), 'origin_xy': t.metadata.get('southwest_pixel_center'),
                      'slope_limit': slope, 'roughness_limit': roughness, 'sky': _sky(terrain_id)}, separators=(',', ':')).encode()
    return raw, gzip.compress(raw, 6)


def _cached_json(request, raw, packed):
    headers = {'Cache-Control': 'public, max-age=3600', 'Vary': 'Accept-Encoding'}
    if 'gzip' in request.headers.get('accept-encoding', ''):
        return Response(packed, media_type='application/json', headers={**headers, 'Content-Encoding': 'gzip'})
    return Response(raw, media_type='application/json', headers=headers)


@app.get('/api/terrain/{terrain_id}')
def terrain_grids(terrain_id: str, request: Request, slope: float = Query(12., gt=0, le=90),
                  roughness: float = Query(1.5, gt=0), footprint: float = Query(30., gt=0)):
    _terrain(terrain_id)
    return _cached_json(request, *_terrain_payload(terrain_id, slope, roughness, footprint))


@lru_cache(maxsize=4)
def _horizon_payload(terrain_id):
    """The nearest surrounding layer, thinned for drawing the landscape around the crop."""
    t = _load(terrain_id)
    if not t.surroundings:
        raw = json.dumps({'rows': 0, 'cols': 0, 'z': []}).encode()
    else:
        ring = t.surroundings[0]
        stride = max(1, int(np.ceil(max(ring.z.shape)/HORIZON_CELLS)))
        z = ring.z[::stride, ::stride]
        raw = json.dumps({'rows': z.shape[0], 'cols': z.shape[1], 'dx': ring.dx*stride, 'dy': ring.dy*stride,
                          'x0': ring.x0, 'y0': ring.y0, 'nodata': -9999., 'z': _grid(z, 0)}, separators=(',', ':')).encode()
    return raw, gzip.compress(raw, 6)


@app.get('/api/terrain/{terrain_id}/horizon')
def terrain_horizon(terrain_id: str, request: Request):
    _terrain(terrain_id)
    return _cached_json(request, *_horizon_payload(terrain_id))


@app.post('/api/sites')
def landing_sites(req: SkyRequest):
    """Best places to land, spread across the map, reachable from the start of the default descent."""
    t = _terrain(req.terrain)
    sky = _sky(req.terrain)
    earth_az, earth_el, sun_az, sun_el = _resolved_sky(req, sky)
    plan = MissionRequest()
    h = _hazards(req.terrain, plan.slope, plan.roughness, plan.footprint)
    vehicle = Vehicle(plan.dry_mass, plan.fuel, plan.max_thrust, plan.isp)
    sx, sy = plan.start_pct[0]/100*t.width, plan.start_pct[1]/100*t.height
    state = {'position': [[sx, sy, float(t.sample(sx, sy))+plan.altitude]], 'velocity': [plan.velocity],
             'mass': [plan.dry_mass+plan.fuel], 't': [0., plan.duration]}
    separation = SITE_SPACING_FRACTION*max(t.width, t.height)
    options, _ = plan_fallbacks(t, h, state, 0, vehicle, count=SITE_CANDIDATES, limit=SITE_CANDIDATES, separation=separation)
    sites = []
    reach = _goal_area(req.terrain)
    for o in options:
        earth = _in_view(t, o['x_m'], o['y_m'], LANDER_ANTENNA_M, earth_az, earth_el)
        sun = _in_view(t, o['x_m'], o['y_m'], LANDER_ANTENNA_M, sun_az, sun_el)
        lat, lon = _lat_lon(t, o['x_m'], o['y_m'])
        row = int(np.clip(round(o['y_m']/t.dy), 0, t.z.shape[0]-1))
        col = int(np.clip(round(o['x_m']/t.dx), 0, t.z.shape[1]-1))
        drive = bool(reach[row, col])
        sites.append({**{k: o[k] for k in ('x_m', 'y_m', 'hazard', 'slope_deg', 'roughness_m', 'fuel_used_kg', 'fuel_remaining_kg')},
                      'z_m': float(t.sample(o['x_m'], o['y_m'])), 'lat': lat, 'lon': lon, 'earth_visible': earth, 'sunlit': sun,
                      'rover_can_reach_goal': drive,
                      'score': o['score']+SITE_NO_VIEW_PENALTY*((not earth)+(not sun))+SITE_STRANDED_PENALTY*(not drive)})
    sites.sort(key=lambda s: s['score'])
    return {'sites': sites[:SITE_COUNT], 'earth': {'azimuth_deg': earth_az, 'elevation_deg': earth_el},
            'sun': {'azimuth_deg': sun_az, 'elevation_deg': sun_el}}


@app.post('/api/point')
def inspect_point(req: PointRequest):
    """What a chosen spot looks like: ground conditions, plus whether Earth and the Sun are in view from it."""
    t = _terrain(req.terrain)
    if not (0 <= req.x <= t.width and 0 <= req.y <= t.height):
        raise HTTPException(422, 'That point is outside the map.')
    earth_az, earth_el, sun_az, sun_el = _resolved_sky(req, _sky(req.terrain))
    plan = MissionRequest()
    h = _hazards(req.terrain, plan.slope, plan.roughness, plan.footprint)
    lat, lon = _lat_lon(t, req.x, req.y)
    return {**_cell_report(t, h, req.x, req.y), 'lat': lat, 'lon': lon,
            'earth_visible': _in_view(t, req.x, req.y, LANDER_ANTENNA_M, earth_az, earth_el),
            'sunlit': _in_view(t, req.x, req.y, LANDER_ANTENNA_M, sun_az, sun_el)}


@app.post('/api/divert')
def divert(req: DivertRequest):
    """Re-route a descending lander from its current state; picks the cheapest feasible timing."""
    t = _terrain(req.terrain)
    if not (0 <= req.target[0] <= t.width and 0 <= req.target[1] <= t.height):
        raise HTTPException(422, 'That point is outside the map.')
    sky = _sky(req.terrain)
    earth_az = sky['earth_az'] if req.earth_az is None else req.earth_az
    earth_el = sky['earth_el'] if req.earth_el is None else req.earth_el
    plan = MissionRequest()
    h = _hazards(req.terrain, plan.slope, plan.roughness, plan.footprint)
    vehicle = Vehicle(plan.dry_mass, plan.fuel, plan.max_thrust, plan.isp)
    end = [req.target[0], req.target[1], float(t.sample(*req.target))]
    if not np.isfinite(end).all():
        raise HTTPException(422, 'That point has no terrain data.')
    best, reasons = None, []
    for factor in (.8, 1., 1.25):
        try:
            route = trajectory(t, req.position, req.velocity, end, max(4., req.remaining_s*factor), req.mass, vehicle)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        if route['feasible'] and (best is None or route['fuel_used'] < best['fuel_used']):
            best = route
        reasons = reasons or route['reasons']
    report = _cell_report(t, h, *req.target)
    if best is None:
        return {'feasible': False, 'reasons': reasons, 'target': report}
    return {'feasible': True, 'reasons': [], 'target': report, 'fuel_used_kg': best['fuel_used'],
            'touchdown': _xyz(best['position'][-1]), **_route_json(best, 120, t, earth_az, earth_el)}


@app.post('/api/mission')
def mission(req: MissionRequest):
    t = _terrain(req.terrain)
    sky = _sky(req.terrain)
    earth_az = sky['earth_az'] if req.earth_az is None else req.earth_az
    earth_el = sky['earth_el'] if req.earth_el is None else req.earth_el
    h = _hazards(req.terrain, req.slope, req.roughness, req.footprint)
    sx, sy = req.start_pct[0]/100*t.width, req.start_pct[1]/100*t.height
    tx, ty = req.target_xy if req.target_xy else (req.target_pct[0]/100*t.width, req.target_pct[1]/100*t.height)
    if not (0 <= tx <= t.width and 0 <= ty <= t.height):
        raise HTTPException(422, 'That landing target is outside the map.')
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
    fallbacks = []
    for rank, o in enumerate(options, 1):
        route = o['route']
        fallbacks.append({'rank': rank, **{k: o[k] for k in ('x_m', 'y_m', 'hazard', 'slope_deg', 'roughness_m',
                                                             'fuel_used_kg', 'fuel_remaining_kg', 'duration_s', 'score')},
                          'touchdown': _xyz(route['position'][-1]), **_route_json(route, 120, t, earth_az, earth_el)})
    return {
        'terrain_id': req.terrain,
        'eligible_pct': float(100*h['safe'].mean()),
        'earth': {'azimuth_deg': earth_az, 'elevation_deg': earth_el},
        'target': _cell_report(t, h, tx, ty),
        'has_dropout': bool(len(blocked)),
        'nominal': {'feasible': nominal['feasible'], 'reasons': nominal['reasons'], 'fuel_used_kg': nominal['fuel_used'],
                    'peak_thrust_n': nominal['peak_thrust'], 'touchdown': _xyz(nominal['position'][-1]), **_route_json(nominal, 200, t, earth_az, earth_el)},
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
