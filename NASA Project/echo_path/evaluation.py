"""Evaluation metrics for the paper: dropout coverage and the nominal / unmitigated / fallback table.

Run with: python -m echo_path.evaluation [--dem PATH] [--earth-az DEG] [--json OUT]
Defaults match the dashboard sidebar so numbers agree with the app.
"""
import argparse
import json
import numpy as np
from .terrain import synthetic, load_dem, load_surround, hazards
from .astro import site_of, sky_limits
from .comms import visibility
from .trajectory import Vehicle, trajectory
from .routing import plan_fallbacks

DEFAULTS = dict(slope=12., roughness=1.5, footprint=30., start=(15, 50), target=(75, 50), altitude=350.,
                duration=120., velocity=(4., 0., -3.), earth_az=270., earth_el=3., samples=31)
LOW_HAZARD = .25


def _point(terrain, pct, height=0.):
    x, y = pct[0]/100*terrain.width, pct[1]/100*terrain.height
    return [x, y, float(terrain.sample(x, y))+height]


def _cell(terrain, point):
    return int(round(point[1]/terrain.dy)), int(round(point[0]/terrain.dx))


def _landing(terrain, hazard, route, vehicle):
    row, col = _cell(terrain, route['position'][-1])
    return {'row': row, 'column': col, 'x_m': float(route['position'][-1, 0]), 'y_m': float(route['position'][-1, 1]),
            'hazard': float(hazard['hazard'][row, col]), 'slope_deg': float(hazard['slope'][row, col]),
            'roughness_m': float(hazard['roughness'][row, col]),
            'fuel_margin_pct': float(100*(route['mass'][-1]-vehicle.dry_mass)/vehicle.fuel)}


def _comms(terrain, route, p):
    indices = np.unique(np.linspace(0, len(route['t'])-1, p['samples']).astype(int))
    return indices, visibility(terrain, route['position'][indices], p['earth_az'], p['earth_el'])


def _windows(times, blocked):
    """Group consecutive blocked samples into (start, end) time spans."""
    spans, begin = [], None
    for i, b in enumerate(blocked):
        if b and begin is None: begin = i
        if begin is not None and (not b or i == len(blocked)-1):
            end = i if b else i-1
            spans.append((float(times[begin]), float(times[end])))
            begin = None
    return spans


def _hazardous_target(terrain, hazard, start, velocity, target, p, vehicle, tries=400):
    """Nearest cell that fails the surface limits yet is still flyable on the nominal plan.

    Stands in for a target ground control would have redirected away from: without
    comms the lander keeps flying to it.
    """
    bad = np.isfinite(terrain.z) & ((hazard['slope'] > p['slope']) | (hazard['roughness'] > p['roughness']))
    cells = np.argwhere(bad)
    if not len(cells): return None, None
    distance = np.hypot(cells[:, 1]*terrain.dx-target[0], cells[:, 0]*terrain.dy-target[1])
    for row, col in cells[np.argsort(distance)[:tries]]:
        end = [col*terrain.dx, row*terrain.dy, float(terrain.z[row, col])]
        route = trajectory(terrain, start, velocity, end, p['duration'], vehicle.dry_mass+vehicle.fuel, vehicle)
        if route['feasible']: return route, end
    return None, None


def slope_agreement(hazard, reference, margin=2):
    """Absolute difference between computed slope and a published slope raster on the same grid."""
    ours, ref = hazard['slope'], reference.z
    if ours.shape != ref.shape:
        raise ValueError(f'Reference slope grid {ref.shape} does not match terrain grid {ours.shape}.')
    inner = np.zeros(ours.shape, bool)
    inner[margin:-margin, margin:-margin] = True
    ok = inner & np.isfinite(ref) & np.isfinite(ours) & np.isfinite(hazard['roughness'])
    diff = np.abs(ours[ok]-ref[ok])
    return {'cells': int(ok.sum()), 'mean_abs_diff_deg': float(diff.mean()),
            'p95_abs_diff_deg': float(np.percentile(diff, 95)), 'max_abs_diff_deg': float(diff.max())}


def evaluate(terrain, vehicle=None, reference_slope=None, **params):
    p = {**DEFAULTS, **params}
    vehicle = vehicle or Vehicle()
    hazard = hazards(terrain, p['slope'], p['roughness'], p['footprint'])
    start, end = _point(terrain, p['start'], p['altitude']), _point(terrain, p['target'])
    if not np.isfinite(start+end).all():
        raise ValueError('Start or target lies on missing DEM data.')
    nominal = trajectory(terrain, start, p['velocity'], end, p['duration'], vehicle.dry_mass+vehicle.fuel, vehicle)
    indices, comms = _comms(terrain, nominal, p)
    times = nominal['t'][indices]
    coverage = []
    for step in np.flatnonzero(comms == 0):
        idx = int(indices[step])
        if idx >= len(nominal['t'])-1 or not nominal['feasible']: continue
        options, _ = plan_fallbacks(terrain, hazard, nominal, idx, vehicle, count=16)
        coverage.append({'time_s': float(nominal['t'][idx]), 'options': len(options),
                         'low_hazard_options': sum(o['hazard'] < LOW_HAZARD for o in options)})
    claim = bool(coverage) and all(c['low_hazard_options'] >= 3 for c in coverage)

    risky, risky_end = _hazardous_target(terrain, hazard, start, p['velocity'], end, p, vehicle)
    unmitigated = fallback = outage_time = None
    if risky is not None:
        unmitigated = _landing(terrain, hazard, risky, vehicle)
        r_indices, r_comms = _comms(terrain, risky, p)
        airborne = [int(r_indices[s]) for s in np.flatnonzero(r_comms == 0) if r_indices[s] < len(risky['t'])-1]
        if airborne:
            outage_time = float(risky['t'][airborne[0]])
            options, _ = plan_fallbacks(terrain, hazard, risky, airborne[0], vehicle)
            if options:
                best = options[0]
                fallback = {k: best[k] for k in ('row', 'column', 'x_m', 'y_m', 'hazard', 'slope_deg', 'roughness_m')}
                fallback['fuel_margin_pct'] = float(100*best['fuel_remaining_kg']/vehicle.fuel)

    result = {'source': terrain.source, 'shape': list(terrain.z.shape), 'dx_m': terrain.dx, 'dy_m': terrain.dy,
              'parameters': {k: list(v) if isinstance(v, tuple) else v for k, v in p.items()},
              'eligible_area_pct': float(100*hazard['safe'].mean()),
              'nominal_feasible': nominal['feasible'], 'nominal_reasons': nominal['reasons'],
              'blocked_samples': int(np.sum(comms == 0)), 'unknown_samples': int(np.sum(comms == -1)),
              'total_samples': len(comms), 'blocked_windows_s': _windows(times, comms == 0),
              'coverage': coverage, 'claim_three_low_hazard': claim,
              'nominal': _landing(terrain, hazard, nominal, vehicle),
              'unmitigated': unmitigated, 'unmitigated_target_m': risky_end, 'outage_time_s': outage_time,
              'fallback': fallback}
    if reference_slope is not None:
        result['slope_agreement'] = slope_agreement(hazard, reference_slope)
    return result


def _fmt(row, key, digits):
    return '—' if row is None else f'{row[key]:.{digits}f}'


def format_markdown(r):
    p = r['parameters']
    lines = [f"## Echo-Path evaluation: {r['source']}", '',
             f"Grid {r['shape'][1]} × {r['shape'][0]} cells at {r['dx_m']:g} × {r['dy_m']:g} m · "
             f"landing-eligible area {r['eligible_area_pct']:.1f}% · Earth/relay azimuth {p['earth_az']:g}°, "
             f"elevation {p['earth_el']:g}°", '']
    if not r['nominal_feasible']:
        lines += [f"**Nominal trajectory fails checks:** {'; '.join(r['nominal_reasons'])}.", '']
    windows = ', '.join(f'{a:.1f}–{b:.1f} s' for a, b in r['blocked_windows_s']) or 'none'
    lines += ['### Communication dropouts', '',
              f"Blocked: {r['blocked_samples']} of {r['total_samples']} samples "
              f"(unknown: {r['unknown_samples']}) · blocked windows: {windows}", '',
              '### Fallback coverage (nominal mission)', '']
    if r['coverage']:
        lines += ['| Outage time (s) | Feasible fallbacks | With H < 0.25 |', '| ---: | ---: | ---: |']
        lines += [f"| {c['time_s']:.1f} | {c['options']} | {c['low_hazard_options']} |" for c in r['coverage']]
        passed = sum(c['low_hazard_options'] >= 3 for c in r['coverage'])
        lines += ['', f"Claim \"at least 3 ranked fallbacks with H < 0.25 at every dropout\": "
                      f"**{'PASS' if r['claim_three_low_hazard'] else 'FAIL'}** ({passed} of {len(r['coverage'])} dropouts)"]
    else:
        lines += ['No airborne blocked samples, so there are no dropouts to cover.']
    n, u, f = r['nominal'], r['unmitigated'], r['fallback']
    lines += ['', '### Results table', '',
              '| Metric | Nominal Flight | Unmitigated Outage | Echo-Path Fallback |', '| --- | ---: | ---: | ---: |',
              f"| Landing hazard score (H) | {_fmt(n, 'hazard', 2)} | {_fmt(u, 'hazard', 2)} | {_fmt(f, 'hazard', 2)} |",
              f"| Fuel margin remaining (%) | {_fmt(n, 'fuel_margin_pct', 1)} | {_fmt(u, 'fuel_margin_pct', 1)} | {_fmt(f, 'fuel_margin_pct', 1)} |",
              f"| Touchdown slope (deg) | {_fmt(n, 'slope_deg', 1)} | {_fmt(u, 'slope_deg', 1)} | {_fmt(f, 'slope_deg', 1)} |", '']
    if u is None:
        lines.append('No flyable hazardous target was found, so the unmitigated scenario could not be built.')
    else:
        outage = 'no airborne dropout occurred' if r['outage_time_s'] is None else f"comms drop at {r['outage_time_s']:.1f} s"
        lines.append(f"Unmitigated scenario: the nominal target is moved to the nearest unsafe cell "
                     f"({u['x_m']:.0f} m, {u['y_m']:.0f} m) that is still flyable; {outage}. "
                     "Without comms the lander lands there; Echo-Path switches to its top-ranked precomputed fallback.")
    if 'slope_agreement' in r:
        s = r['slope_agreement']
        lines += ['', '### Slope check against the published slope map', '',
                  f"Over {s['cells']} cells: mean absolute difference {s['mean_abs_diff_deg']:.2f}°, "
                  f"95th percentile {s['p95_abs_diff_deg']:.2f}°, maximum {s['max_abs_diff_deg']:.2f}°."]
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--dem', help='Projected lunar GeoTIFF; synthetic terrain when omitted')
    parser.add_argument('--row', type=int, default=0, help='DEM crop start row (from north)')
    parser.add_argument('--col', type=int, default=0, help='DEM crop start column (from west)')
    parser.add_argument('--size', type=int, default=240, help='DEM crop size in pixels')
    parser.add_argument('--surround', action='append', default=[], metavar='PATH',
                        help='Coarser DEM for distant horizons, finest first; repeatable. Earth then defaults to its mean position at the site')
    parser.add_argument('--earth-az', type=float)
    parser.add_argument('--earth-el', type=float)
    parser.add_argument('--reference-slope', help='Published slope GeoTIFF on the same grid as --dem')
    parser.add_argument('--json', help='Also write the full results to this JSON file')
    args = parser.parse_args(argv)
    terrain = load_dem(args.dem, args.row, args.col, args.size) if args.dem else synthetic()
    terrain.surroundings = [load_surround(path, terrain) for path in args.surround]
    reference = load_dem(args.reference_slope, args.row, args.col, args.size) if args.reference_slope else None
    earth_az, earth_el = DEFAULTS['earth_az'], DEFAULTS['earth_el']
    if terrain.surroundings:
        earth = sky_limits(*site_of(terrain))['earth']
        earth_az, earth_el = earth['mean_az'] % 360, earth['mean_el']
    result = evaluate(terrain, reference_slope=reference,
                      earth_az=earth_az if args.earth_az is None else args.earth_az,
                      earth_el=earth_el if args.earth_el is None else args.earth_el)
    print(format_markdown(result))
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump(result, fh, indent=2)


if __name__ == '__main__':
    main()
