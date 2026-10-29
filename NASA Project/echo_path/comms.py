import numpy as np


def visibility(terrain, points, azimuth_deg=270., elevation_deg=3.):
    """1=clear within tile, 0=blocked, -1=unknown through missing DEM.

    Azimuth clockwise from grid north. Local flat surface approximation.
    """
    points = np.asarray(points)
    if elevation_deg <= 0:
        return np.zeros(len(points), dtype=int)
    if elevation_deg >= 89.99:
        ground = terrain.sample(points[:, 0], points[:, 1])
        return np.where(np.isfinite(ground), (points[:, 2] >= ground).astype(int), -1)
    az = np.radians(azimuth_deg)
    ux, uy = np.sin(az), np.cos(az)
    distance = np.arange(0, np.hypot(terrain.width, terrain.height)+min(terrain.dx, terrain.dy), min(terrain.dx, terrain.dy)/2)
    x = points[:, 0, None] + ux*distance
    y = points[:, 1, None] + uy*distance
    inside = (x >= 0) & (x <= terrain.width) & (y >= 0) & (y <= terrain.height)
    ground = terrain.sample(x, y)
    ray_z = points[:, 2, None] + np.tan(np.radians(elevation_deg))*distance
    blocked = np.any(inside & np.isfinite(ground) & (ground > ray_z+1e-5), axis=1)
    unknown = np.any(inside & ~np.isfinite(ground), axis=1)
    return np.where(blocked, 0, np.where(unknown, -1, 1))


def shadow_map(terrain, azimuth, elevation):
    y, x = np.indices(terrain.z.shape)
    points = np.column_stack((x.ravel()*terrain.dx, y.ravel()*terrain.dy, terrain.z.ravel()+.1))
    chunks = [visibility(terrain, points[i:i+250], azimuth, elevation) for i in range(0, len(points), 250)]
    return np.concatenate(chunks).reshape(terrain.z.shape)
