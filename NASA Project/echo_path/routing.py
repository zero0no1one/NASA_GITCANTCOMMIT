import numpy as np
from .trajectory import trajectory


def candidates(terrain, hazard, start, limit=16):
    cells = np.argwhere(hazard['safe'])
    if not len(cells): return []
    distance = np.hypot(cells[:, 1]*terrain.dx-start[0], cells[:, 0]*terrain.dy-start[1])
    score = hazard['hazard'][cells[:, 0], cells[:, 1]] + .25*distance/max(terrain.width, terrain.height)
    selected = []
    separation = 4*max(terrain.dx, terrain.dy)
    # Always evaluate the nearest eligible site: late outages may permit only
    # a tiny divert even when a distant flatter site has a better heuristic score.
    order = np.concatenate(([np.argmin(distance)], np.argsort(score)))
    for idx in order:
        row, col = cells[idx]
        point = np.array([col*terrain.dx, row*terrain.dy, terrain.z[row, col]])
        if all(np.linalg.norm(point[:2]-p[2][:2]) >= separation for p in selected):
            selected.append((int(row), int(col), point))
        if len(selected) >= limit: break
    return selected


def plan_fallbacks(terrain, hazard, nominal, index, vehicle, count=3):
    start = nominal['position'][index]
    velocity = nominal['velocity'][index]
    mass = nominal['mass'][index]
    remaining = nominal['t'][-1]-nominal['t'][index]
    if remaining < 2 or mass <= vehicle.dry_mass:
        return [], {'tested': 0, 'rejected': {'No flight time or fuel remaining': 1}}
    results, rejected, tested = [], {}, 0
    for row, col, point in candidates(terrain, hazard, start):
        best = None
        for factor in (.8, 1., 1.25):
            route = trajectory(terrain, start, velocity, point, max(4, remaining*factor), mass, vehicle)
            tested += 1
            if not route['feasible']:
                for reason in route['reasons']: rejected[reason] = rejected.get(reason, 0)+1
                continue
            cost = float(hazard['hazard'][row, col] + .4*route['fuel_used']/max(mass-vehicle.dry_mass, 1))
            result = {'row': row, 'column': col, 'x_m': float(point[0]), 'y_m': float(point[1]),
                      'hazard': float(hazard['hazard'][row, col]), 'slope_deg': float(hazard['slope'][row, col]),
                      'roughness_m': float(hazard['roughness'][row, col]), 'fuel_used_kg': route['fuel_used'],
                      'fuel_remaining_kg': float(route['mass'][-1]-vehicle.dry_mass),
                      'duration_s': float(route['t'][-1]), 'score': cost, 'route': route}
            if best is None or cost < best['score']: best = result
        if best: results.append(best)
    return sorted(results, key=lambda r: r['score'])[:count], {'tested': tested, 'rejected': rejected}
