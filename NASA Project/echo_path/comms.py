import numpy as np
from .terrain import MOON_RADIUS_M


def _blocked_beyond(terrain, points, ux, uy, tan_el):
    """Rays stopped by terrain outside the crop, allowing for the Moon curving away below them."""
    blocked = np.zeros(len(points), bool)
    boxes = [(0., terrain.width, 0., terrain.height)]
    for ring in terrain.surroundings:
        todo = np.flatnonzero(~blocked)
        if not len(todo): break
        # Furthest distance at which this layer's highest ground could still reach the lowest ray.
        rise = np.nanmax(ring.z)-points[todo, 2].min()
        if rise > 0:
            end = MOON_RADIUS_M*(np.sqrt(tan_el**2+2*rise/MOON_RADIUS_M)-tan_el)
            step = min(ring.dx, ring.dy)
            d = np.arange(step, end+step, step)
            x = points[todo, 0, None]+ux*d
            y = points[todo, 1, None]+uy*d
            finer = np.zeros(x.shape, bool)
            for left, right, south, north in boxes:
                finer |= (x >= left) & (x <= right) & (y >= south) & (y <= north)
            ground = ring.sample(x, y)-d*d/(2*MOON_RADIUS_M)
            ray_z = points[todo, 2, None]+tan_el*d
            blocked[todo] = np.any(~finer & np.isfinite(ground) & (ground > ray_z), axis=1)
        boxes.append(ring.box)
    return blocked


def visibility(terrain, points, azimuth_deg=270., elevation_deg=3., surroundings=True):
    """1=clear of all known terrain, 0=blocked, -1=unknown through missing DEM.

    Azimuth clockwise from grid north. The crop itself uses a local flat surface;
    any terrain.surroundings extend the check to distant horizons with lunar curvature.
    """
    points = np.asarray(points)
    if elevation_deg <= 0:
        return np.zeros(len(points), dtype=int)
    if elevation_deg >= 89.99:
        ground = terrain.sample(points[:, 0], points[:, 1])
        return np.where(np.isfinite(ground), (points[:, 2] >= ground).astype(int), -1)
    az = np.radians(azimuth_deg)
    ux, uy = np.sin(az), np.cos(az)
    tan_el = np.tan(np.radians(elevation_deg))
    distance = np.arange(0, np.hypot(terrain.width, terrain.height)+min(terrain.dx, terrain.dy), min(terrain.dx, terrain.dy)/2)
    x = points[:, 0, None] + ux*distance
    y = points[:, 1, None] + uy*distance
    inside = (x >= 0) & (x <= terrain.width) & (y >= 0) & (y <= terrain.height)
    ground = terrain.sample(x, y)
    ray_z = points[:, 2, None] + tan_el*distance
    blocked = np.any(inside & np.isfinite(ground) & (ground > ray_z+1e-5), axis=1)
    unknown = np.any(inside & ~np.isfinite(ground), axis=1)
    if surroundings and terrain.surroundings:
        blocked |= _blocked_beyond(terrain, points, ux, uy, tan_el)
    return np.where(blocked, 0, np.where(unknown, -1, 1))


def shadow_map(terrain, azimuth, elevation, far_stride=8, stride=1):
    """Sunlight per cell. Distant horizons change slowly across a crop, so they are checked every far_stride cells.

    stride > 1 casts rays from every stride-th cell and repeats the result: much faster, and
    enough to steer a route, but use the default wherever exact per-cell eligibility matters.
    """
    rows, cols = np.arange(0, terrain.z.shape[0], stride), np.arange(0, terrain.z.shape[1], stride)
    y, x = np.meshgrid(rows, cols, indexing='ij')
    points = np.column_stack((x.ravel()*terrain.dx, y.ravel()*terrain.dy, terrain.z[y, x].ravel()+.1))
    chunks = [visibility(terrain, points[i:i+250], azimuth, elevation, surroundings=False) for i in range(0, len(points), 250)]
    light = np.concatenate(chunks).reshape(y.shape)
    light = np.repeat(np.repeat(light, stride, 0), stride, 1)[:terrain.z.shape[0], :terrain.z.shape[1]]
    if terrain.surroundings and 0 < elevation < 89.99:
        rows, cols = np.arange(0, terrain.z.shape[0], far_stride), np.arange(0, terrain.z.shape[1], far_stride)
        rr, cc = np.meshgrid(rows, cols, indexing='ij')
        coarse = np.column_stack((cc.ravel()*terrain.dx, rr.ravel()*terrain.dy, terrain.z[rr, cc].ravel()+.1))
        az = np.radians(azimuth)
        far = _blocked_beyond(terrain, coarse[np.isfinite(coarse[:, 2])], np.sin(az), np.cos(az), np.tan(np.radians(elevation)))
        shade = np.zeros(rr.size, bool)
        shade[np.isfinite(coarse[:, 2])] = far
        shade = shade.reshape(rr.shape)
        light[np.repeat(np.repeat(shade, far_stride, 0), far_stride, 1)[:light.shape[0], :light.shape[1]]] = 0
    return light
