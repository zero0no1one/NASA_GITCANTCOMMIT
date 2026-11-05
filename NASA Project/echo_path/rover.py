"""Rover traverse planning: A* over a traversability grid, then a timed drive with comms, sunlight and battery.

Run with: python -m echo_path.rover [--dem PATH] [--start X Y] [--goal X Y]
Coordinates follow the rest of the engine: x = col*dx, y = row*dy, row 0 south,
azimuth clockwise from grid north.
"""
import argparse
import heapq
from dataclasses import dataclass
import numpy as np
from scipy.ndimage import map_coordinates
from .terrain import synthetic, load_dem, load_surround, hazards
from .astro import site_of, sky_limits
from .comms import visibility, shadow_map


@dataclass(frozen=True)
class Rover:
    max_slope: float = 20.
    max_roughness: float = 1.
    speed: float = .5             # m/s on flat ground; demo pace, real rovers drive ~0.1-0.2 m/s
    min_speed_frac: float = .3    # speed floor on steep ground
    antenna_height: float = 1.5
    panel_height: float = 1.
    battery_wh: float = 600.
    start_battery_pct: float = 100.
    drive_w: float = 150.
    idle_w: float = 40.
    solar_w: float = 200.
    shadow_penalty: float = 1.
    footprint: float = 10.        # roughness window (m)


def traversability(terrain, rover, sun_az=None, sun_el=None):
    """Per-cell cost >= 1, or inf where the rover cannot drive."""
    h = hazards(terrain, rover.max_slope, rover.max_roughness, rover.footprint)
    slope, rough = h['slope'], h['roughness']
    blocked = ~np.isfinite(terrain.z) | ~np.isfinite(rough) | (slope > rover.max_slope) | (rough > rover.max_roughness)
    cost = 1 + 2*slope/rover.max_slope + np.nan_to_num(rough)/rover.max_roughness
    shadowed = np.zeros(terrain.z.shape, bool)
    if sun_el is not None:
        shadowed = shadow_map(terrain, sun_az, sun_el) != 1
        cost = cost + rover.shadow_penalty*shadowed
    cost[blocked] = np.inf
    return {'cost': cost, 'blocked': blocked, 'slope': slope, 'shadowed': shadowed}


def astar(cost, start, goal, dx=1., dy=1.):
    """8-connected A* on a cost grid; step cost is length x mean cell cost. Returns [(row, col), ...] or None."""
    rows, cols = cost.shape
    if not (np.isfinite(cost[start]) and np.isfinite(cost[goal])):
        return None
    flat = cost.ravel()
    moves = [(dr, dc, np.hypot(dr*dy, dc*dx)) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]
    gr, gc = goal
    g = np.full(flat.size, np.inf)
    parent = np.full(flat.size, -1, dtype=np.int64)
    s = start[0]*cols+start[1]
    g[s] = 0.
    # Every step costs at least its length (cell cost >= 1), so straight-line distance is admissible.
    frontier = [(np.hypot((gr-start[0])*dy, (gc-start[1])*dx), 0., s)]
    goal_index = gr*cols+gc
    while frontier:
        _, gs, i = heapq.heappop(frontier)
        if i == goal_index: break
        if gs > g[i]: continue
        r, c = divmod(i, cols)
        for dr, dc, length in moves:
            nr, nc = r+dr, c+dc
            if not (0 <= nr < rows and 0 <= nc < cols): continue
            j = nr*cols+nc
            if flat[j] == np.inf: continue
            # Diagonals may not cut between two blocked cells.
            if dr and dc and flat[r*cols+nc] == np.inf and flat[nr*cols+c] == np.inf: continue
            new = gs + length*(flat[i]+flat[j])/2
            if new < g[j]:
                g[j], parent[j] = new, i
                heapq.heappush(frontier, (new+np.hypot((gr-nr)*dy, (gc-nc)*dx), new, j))
    if not np.isfinite(g[goal_index]):
        return None
    path, i = [], goal_index
    while i != -1:
        path.append(divmod(int(i), cols))
        i = parent[i]
    return path[::-1]


def line_cost(cost, a, b, dx=1., dy=1.):
    """Cost of driving straight between two cells, on the same scale as astar(); inf if it crosses a blocked cell."""
    n = int(max(abs(b[0]-a[0]), abs(b[1]-a[1])))*2+1
    if n < 2: return 0.
    values = cost[np.rint(np.linspace(a[0], b[0], n)).astype(int), np.rint(np.linspace(a[1], b[1], n)).astype(int)]
    return float(np.hypot((b[0]-a[0])*dy, (b[1]-a[1])*dx)*(values[:-1]+values[1:]).sum()/(2*(n-1)))


def smooth(path, cost, dx=1., dy=1.):
    """Drop grid zig-zags: take a straight shortcut only where it costs no more than the A* route it replaces."""
    if len(path) < 3: return list(path)
    # Same step formula as astar(), so the running total stays finite even beside blocked cells.
    steps = [np.hypot((b[0]-a[0])*dy, (b[1]-a[1])*dx)*(cost[a]+cost[b])/2 for a, b in zip(path[:-1], path[1:])]
    along = np.concatenate(([0.], np.cumsum(steps)))
    out, i = [path[0]], 0
    while i < len(path)-1:
        j = len(path)-1
        while j > i+1 and line_cost(cost, path[i], path[j], dx, dy) > along[j]-along[i]: j -= 1
        out.append(path[j])
        i = j
    return out


def drive(terrain, corners, grid, rover, earth_az, earth_el, sun_az=None, sun_el=None):
    """Resample the corner polyline and attach time, speed, heading, comms, sunlight and battery."""
    xy = np.array([[c*terrain.dx, r*terrain.dy] for r, c in corners], float)
    step = min(terrain.dx, terrain.dy)
    pts, bounds = [xy[0]], [0]
    for k in range(len(xy)-1):
        n = max(1, int(np.ceil(np.linalg.norm(xy[k+1]-xy[k])/step)))
        pts.extend(xy[k]+(xy[k+1]-xy[k])*s/n for s in range(1, n+1))
        bounds.append(len(pts)-1)
    pts = np.array(pts)
    z = terrain.sample(pts[:, 0], pts[:, 1])
    slope = map_coordinates(grid['slope'], [pts[:, 1]/terrain.dy, pts[:, 0]/terrain.dx], order=1, mode='nearest')
    seg = np.diff(pts, axis=0)
    seg_len = np.hypot(seg[:, 0], seg[:, 1])
    heading = np.degrees(np.arctan2(seg[:, 0], seg[:, 1])) % 360
    pitch = np.degrees(np.arctan2(np.diff(z), np.maximum(seg_len, 1e-9)))
    speed = rover.speed*np.maximum(rover.min_speed_frac, 1-slope/rover.max_slope)
    dt = seg_len/speed[:-1]
    t = np.concatenate(([0.], np.cumsum(dt)))
    comms = visibility(terrain, np.column_stack((pts, z+rover.antenna_height)), earth_az, earth_el)
    if sun_el is None:
        sunlit = np.ones(len(pts), bool)
    else:
        sunlit = visibility(terrain, np.column_stack((pts, z+rover.panel_height)), sun_az, sun_el) == 1
    net_w = rover.drive_w+rover.idle_w-rover.solar_w*sunlit[:-1]
    # Integrate step by step: charge above full is lost, and the rover stops when the battery empties.
    battery, stop = np.full(len(pts), float(rover.start_battery_pct)), None
    for i, used in enumerate(net_w*dt/3600*100/rover.battery_wh):
        level = min(100., battery[i]-used)
        if level <= 0:
            stop = i if battery[i] <= 0 else i+1
            battery[i+1] = 0.
            break
        battery[i+1] = level
    keep = len(pts) if stop is None else stop+1
    heading = np.append(heading, heading[-1] if len(heading) else 0.)
    pitch = np.append(pitch, pitch[-1] if len(pitch) else 0.)
    timeline = {'t': t, 'x': pts[:, 0], 'y': pts[:, 1], 'z': z, 'heading_deg': heading, 'pitch_deg': pitch,
                'speed_m_s': speed, 'comms': comms, 'sunlit': sunlit, 'battery_pct': battery}
    timeline = {key: values[:keep] for key, values in timeline.items()}
    segments = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        if a >= keep-1: break
        b = min(b, keep-1)
        segments.append({'start_s': float(t[a]), 'end_s': float(t[b]), 'length_m': float(seg_len[a:b].sum()),
                         'heading_deg': float(heading[a]), 'mean_speed_m_s': float(seg_len[a:b].sum()/max(t[b]-t[a], 1e-9))})
    return timeline, segments, (None if stop is None else float(t[stop]))


def _round(timeline):
    out = {}
    for key, values in timeline.items():
        values = np.asarray(values)
        if values.dtype == bool: out[key] = values.tolist()
        elif np.issubdtype(values.dtype, np.integer): out[key] = values.astype(int).tolist()
        else: out[key] = np.round(values.astype(float), 3).tolist()
    return out


def plan_rover(terrain, start_xy, goal_xy, rover=None, earth_az=270., earth_el=3., sun_az=None, sun_el=None, grid=None):
    """Plan and time a traverse. Pass a precomputed traversability `grid` to skip recomputing it."""
    rover = rover or Rover()
    if min(rover.speed, rover.max_slope, rover.max_roughness, rover.battery_wh) <= 0 or not 0 < rover.min_speed_frac <= 1:
        raise ValueError('Rover speed, limits and battery capacity must be positive, and the speed floor between 0 and 1.')
    grid = grid or traversability(terrain, rover, sun_az, sun_el)
    rows, cols = terrain.z.shape

    def cell(xy):
        return int(round(xy[1]/terrain.dy)), int(round(xy[0]/terrain.dx))

    start, goal = cell(start_xy), cell(goal_xy)
    for name, (r, c) in (('Start', start), ('Goal', goal)):
        if not (0 <= r < rows and 0 <= c < cols):
            return {'feasible': False, 'reason': f'{name} is outside the terrain.'}
        if grid['blocked'][r, c]:
            return {'feasible': False, 'reason': f'{name} is on ground the rover cannot drive (too steep, rough or unknown).'}
    path = astar(grid['cost'], start, goal, terrain.dx, terrain.dy)
    if path is None:
        return {'feasible': False, 'reason': 'No traversable route between start and goal.'}
    corners = smooth(path, grid['cost'], terrain.dx, terrain.dy)
    if len(corners) == 1:
        corners = corners*2
    timeline, segments, depleted_at = drive(terrain, corners, grid, rover, earth_az, earth_el, sun_az, sun_el)
    dt = np.diff(timeline['t'])
    duration = float(timeline['t'][-1])
    share = lambda mask: float(100*dt[mask[:-1]].sum()/duration) if duration > 0 else 0.
    summary = {'distance_m': float(sum(s['length_m'] for s in segments)), 'duration_s': duration,
               'min_battery_pct': float(timeline['battery_pct'].min()), 'end_battery_pct': float(timeline['battery_pct'][-1]),
               'comms_blocked_pct': share(timeline['comms'] != 1), 'shadow_pct': share(~timeline['sunlit']),
               'grid_steps': len(path), 'corners': len(corners)}
    reason = None if depleted_at is None else f'Battery depleted at {depleted_at:.0f} s; the rover stopped short of the goal.'
    return {'feasible': depleted_at is None, 'reached_goal': depleted_at is None, 'reason': reason, 'summary': summary,
            'segments': segments, 'timeline': _round(timeline)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--dem', help='Projected lunar GeoTIFF; synthetic terrain when omitted')
    parser.add_argument('--size', type=int, default=240)
    parser.add_argument('--start', type=float, nargs=2, metavar=('X', 'Y'), help='Start in metres (default: 75%%, 50%% of the tile)')
    parser.add_argument('--goal', type=float, nargs=2, metavar=('X', 'Y'), help='Goal in metres (default: 90%%, 90%% of the tile)')
    parser.add_argument('--surround', action='append', default=[], metavar='PATH',
                        help='Coarser DEM for distant horizons, finest first; repeatable. Earth and Sun then default to real values for the site')
    parser.add_argument('--earth-az', type=float)
    parser.add_argument('--earth-el', type=float)
    parser.add_argument('--sun-az', type=float, default=90.)
    parser.add_argument('--sun-el', type=float)
    args = parser.parse_args(argv)
    terrain = load_dem(args.dem, size=args.size) if args.dem else synthetic()
    terrain.surroundings = [load_surround(path, terrain) for path in args.surround]
    earth_az, earth_el, sun_el = 270., 3., 5.
    if terrain.surroundings:
        sky = sky_limits(*site_of(terrain))
        earth_az, earth_el, sun_el = sky['earth']['mean_az'] % 360, sky['earth']['mean_el'], .8*sky['sun']['el_max']
    start = args.start or (.75*terrain.width, .5*terrain.height)
    goal = args.goal or (.9*terrain.width, .9*terrain.height)
    r = plan_rover(terrain, start, goal, earth_az=earth_az if args.earth_az is None else args.earth_az,
                   earth_el=earth_el if args.earth_el is None else args.earth_el,
                   sun_az=args.sun_az, sun_el=sun_el if args.sun_el is None else args.sun_el)
    if not r.get('summary'):
        print(r['reason'])
        return
    s = r['summary']
    print(f"{terrain.source}: {s['distance_m']:.0f} m in {s['duration_s']/60:.1f} min over {len(r['segments'])} legs; "
          f"battery {s['end_battery_pct']:.0f}% at end (min {s['min_battery_pct']:.0f}%); "
          f"comms blocked {s['comms_blocked_pct']:.0f}% of the time; in shadow {s['shadow_pct']:.0f}%")
    for seg in r['segments']:
        print(f"  {seg['start_s']:7.1f}-{seg['end_s']:7.1f} s  heading {seg['heading_deg']:5.1f} deg  "
              f"{seg['length_m']:6.1f} m at {seg['mean_speed_m_s']:.2f} m/s")
    if r['reason']:
        print(r['reason'])


if __name__ == '__main__':
    main()
