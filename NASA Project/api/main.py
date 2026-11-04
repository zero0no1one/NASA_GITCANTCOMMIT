"""Echo-Path HTTP API for the 3D web app.

Run from "NASA Project":  python -m uvicorn api.main:app --reload
Grids are flattened row-major with row 0 at the south edge; x = col*dx, y = row*dy, in metres.
"""
from dataclasses import asdict, replace
from functools import lru_cache
from pathlib import Path
from typing import Optional
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from echo_path.terrain import synthetic, load_dem, hazards
from echo_path.comms import visibility
from echo_path.trajectory import Vehicle, trajectory
from echo_path.routing import plan_fallbacks
from echo_path.rover import Rover, traversability, plan_rover

DATA = Path(__file__).resolve().parents[1] / 'data'
TERRAINS = {
    'synthetic': {'label': 'Synthetic ridge and landing basin', 'earth_az': 270.,
                  'load': lambda: synthetic()},
    'lola_site04': {'label': 'LOLA south pole, PGDA Site04 crop (89.48°S, 156.05°W)', 'earth_az': 0.,
                    'load': lambda: load_dem(str(DATA/'lola_site04_r2960_c400.tif'), size=240)},
}
SAMPLES = 31

app = FastAPI(title='Echo-Path API')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
                   allow_methods=['*'], allow_headers=['*'])


def _terrain(terrain_id):
    if terrain_id not in TERRAINS:
        raise HTTPException(404, f'Unknown terrain {terrain_id!r}.')
    return _load(terrain_id)


@lru_cache(maxsize=None)
def _load(terrain_id):
    return TERRAINS[terrain_id]['load']()


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


class MissionRequest(BaseModel):
    terrain: str = 'synthetic'
    slope: float = 12.
    roughness: float = 1.5
    footprint: float = 30.
    start_pct: tuple[float, float] = (15., 50.)
    target_pct: tuple[float, float] = (75., 50.)
    altitude: float = 350.
    duration: float = 120.
    velocity: tuple[float, float, float] = (4., 0., -3.)
    dry_mass: float = 700.
    fuel: float = 300.
    max_thrust: float = 5000.
    isp: float = 310.
    earth_az: Optional[float] = None
    earth_el: float = 3.
    outage_step: Optional[int] = Field(None, ge=0, lt=SAMPLES, description='Comms sample to fail; default is the first blocked one')


class RoverRequest(BaseModel):
    terrain: str = 'synthetic'
    start: tuple[float, float]
    goal: tuple[float, float]
    earth_az: Optional[float] = None
    earth_el: float = 3.
    sun_az: Optional[float] = 90.
    sun_el: Optional[float] = 5.
    max_slope: float = 20.
    max_roughness: float = 1.
    speed: float = .5
    start_battery_pct: float = Field(100., ge=0, le=100)


@app.get('/api/terrains')
def terrains():
    out = []
    for key, spec in TERRAINS.items():
        t = _load(key)
        out.append({'id': key, 'label': spec['label'], 'rows': t.z.shape[0], 'cols': t.z.shape[1],
                    'dx': t.dx, 'dy': t.dy, 'width_m': t.width, 'height_m': t.height, 'earth_az': spec['earth_az']})
    return out


@app.post('/api/mission')
def mission(req: MissionRequest):
    t = _terrain(req.terrain)
    earth_az = TERRAINS[req.terrain]['earth_az'] if req.earth_az is None else req.earth_az
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
    comms = visibility(t, nominal['position'][samples], earth_az, req.earth_el)
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
                    'z': _grid(t.z, 2), 'hazard': _grid(h['hazard'], 3), 'slope': _grid(h['slope'], 2)},
        'eligible_pct': float(100*h['safe'].mean()),
        'earth': {'azimuth_deg': earth_az, 'elevation_deg': req.earth_el},
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
    earth_az = TERRAINS[req.terrain]['earth_az'] if req.earth_az is None else req.earth_az
    spec = replace(Rover(), max_slope=req.max_slope, max_roughness=req.max_roughness, speed=req.speed,
                   start_battery_pct=req.start_battery_pct)
    sun_az, sun_el = (req.sun_az, req.sun_el) if req.sun_el is not None else (None, None)
    grid = _rover_grid(req.terrain, spec, sun_az, sun_el)
    result = plan_rover(t, req.start, req.goal, spec, earth_az, req.earth_el, sun_az, sun_el, grid=grid)
    result['rover'] = asdict(spec)
    result['earth'] = {'azimuth_deg': earth_az, 'elevation_deg': req.earth_el}
    result['sun'] = None if sun_el is None else {'azimuth_deg': sun_az, 'elevation_deg': sun_el}
    return result
