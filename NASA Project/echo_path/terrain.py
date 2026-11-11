from dataclasses import dataclass, field
import numpy as np
from scipy.ndimage import map_coordinates, uniform_filter, binary_erosion


MOON_RADIUS_M = 1737400.


@dataclass
class Surround:
    """Coarser DEM around a crop, used only for distant horizons. (x0, y0) is its south-west pixel centre in crop metres."""
    z: np.ndarray
    dx: float
    dy: float
    x0: float
    y0: float

    @property
    def box(self):
        return self.x0, self.x0+(self.z.shape[1]-1)*self.dx, self.y0, self.y0+(self.z.shape[0]-1)*self.dy

    def sample(self, x, y):
        x, y = np.broadcast_arrays(x, y)
        return map_coordinates(self.z, [(y.ravel()-self.y0)/self.dy, (x.ravel()-self.x0)/self.dx],
                               order=1, mode='constant', cval=np.nan).reshape(x.shape)


@dataclass
class Terrain:
    z: np.ndarray
    dx: float
    dy: float
    source: str
    metadata: dict = field(default_factory=dict)
    surroundings: list = field(default_factory=list)   # Surround layers, nearest and finest first

    @property
    def width(self):
        return (self.z.shape[1] - 1) * self.dx

    @property
    def height(self):
        return (self.z.shape[0] - 1) * self.dy

    def sample(self, x, y):
        x, y = np.broadcast_arrays(x, y)
        return map_coordinates(self.z, [y.ravel() / self.dy, x.ravel() / self.dx],
                               order=1, mode='constant', cval=np.nan).reshape(x.shape)


def synthetic(seed=42, size=101, spacing=10.):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[:size, :size] * spacing
    span = (size - 1) * spacing
    # A ridge between the approach and the flat landing basin creates late occlusion.
    z = 65 * np.exp(-((x - .45 * span) / (.055 * span)) ** 2)
    z += 3 * np.sin(x / 110) * np.cos(y / 140)
    for _ in range(6):
        cx, cy = rng.uniform(0, span, 2)
        radius = rng.uniform(20, 55)
        z -= rng.uniform(4, 12) * np.exp(-((x-cx)**2+(y-cy)**2)/(2*radius**2))
    return Terrain(z, spacing, spacing, 'Synthetic ridge and landing basin', {'seed': seed})


def random_moon(seed, size=121, spacing=10.):
    """A made-up patch of lunar surface, the same every time for the same seed.

    Rolling ground whose relief fades with smaller scales, craters with raised rims in the size mix seen on old
    lunar surfaces (many small, few large; fresh ones deep, old ones worn shallow), boulders around fresh craters,
    and sometimes a ridge. Also picks a rover goal: firm ground just outside the rim of the largest crater.
    """
    rng = np.random.default_rng(seed)
    span = (size-1)*spacing
    y, x = np.mgrid[:size, :size]*spacing

    # Rolling ground: random relief with power falling off steeply with frequency.
    f = np.hypot(np.fft.fftfreq(size, spacing)[None, :], np.fft.fftfreq(size, spacing)[:, None])
    f[0, 0] = np.inf
    amplitude = f**(-rng.uniform(1.7, 2.0))
    ground = np.real(np.fft.ifft2(amplitude*(rng.normal(size=f.shape)+1j*rng.normal(size=f.shape))))
    z = ground/ground.std()*rng.uniform(4., 10.)
    tilt = np.radians(rng.uniform(0., 1.5))
    heading = rng.uniform(0., 2*np.pi)
    z += np.tan(tilt)*(x*np.cos(heading)+y*np.sin(heading))

    # Sometimes a ridge crosses the map: it hides the horizon and makes the rover go round.
    if rng.random() < .6:
        angle = rng.uniform(0., np.pi)
        cx, cy = rng.uniform(.25, .75, 2)*span
        across = (x-cx)*np.sin(angle)-(y-cy)*np.cos(angle)
        along = (x-cx)*np.cos(angle)+(y-cy)*np.sin(angle)
        width = rng.uniform(60., 130.)
        swell = 1+.35*np.sin(along/rng.uniform(120., 260.)+rng.uniform(0., 2*np.pi))
        z += rng.uniform(25., 60.)*swell*np.exp(-(across/width)**2)

    # Craters: sizes from a power law with exponent -2 (cumulative), oldest first so younger ones cut into them.
    d_min, d_max = 20., rng.uniform(250., 450.)
    u = rng.random(rng.integers(50, 110))
    diameters = d_min*(1-u*(1-(d_min/d_max)**2))**-.5
    craters = []
    for d, fresh in sorted(zip(diameters, rng.random(len(diameters))), key=lambda c: c[1]):
        cx, cy = rng.uniform(-.1, 1.1, 2)*span
        radius = d/2
        depth = d*(.04+.16*fresh)
        rim = d*(.008+.032*fresh)
        s = np.hypot(x-cx, y-cy)/radius
        z += np.where(s < 1, -depth+(depth+rim)*s**2, rim*np.maximum(s, 1)**-3)
        craters.append((cx, cy, radius, fresh))

    # Boulders: thrown out around fresh craters, plus a scattering everywhere.
    spots = [(rng.uniform(0., span), rng.uniform(0., span), rng.uniform(.4, 1.8)) for _ in range(rng.integers(20, 60))]
    for cx, cy, radius, fresh in craters:
        if fresh > .6 and radius > 30:
            for _ in range(int(fresh*radius/6)):
                a, r = rng.uniform(0., 2*np.pi), radius*rng.uniform(.9, 2.)
                spots.append((cx+r*np.cos(a), cy+r*np.sin(a), rng.uniform(1., 3.5)))
    for bx, by, height in spots:
        z += height*np.exp(-((x-bx)**2+(y-by)**2)/(2*rng.uniform(3., 6.)**2))

    terrain = Terrain(z-z.min(), spacing, spacing, f'Random lunar surface, seed {seed}', {'seed': seed})
    terrain.metadata['goal_xy'] = _crater_goal(terrain, craters)
    return terrain


def _crater_goal(terrain, craters):
    """Firm ground just outside the largest crater rim well inside the map, else the far corner.

    Either way the goal is on the largest stretch of connected drivable ground, with margin below the rover's
    default limits (20° slope, 1 m roughness over 10 m), so a route from a landing site normally exists.
    """
    from scipy.ndimage import label
    h = hazards(terrain, 20., 1., 10.)
    drivable = np.isfinite(h['roughness']) & (h['slope'] < 14.) & (h['roughness'] < .6)
    parts, count = label(drivable)   # edge-connected, like the rover's route search
    if count == 0:
        return [.85*terrain.width, .85*terrain.height]
    largest = parts == np.argmax(np.bincount(parts.ravel())[1:])+1
    firm = binary_erosion(largest, structure=np.ones((3, 3)))
    rows, cols = terrain.z.shape
    span = terrain.width

    def cell(px, py):
        return int(round(py/terrain.dy)), int(round(px/terrain.dx))

    for cx, cy, radius, _ in sorted(craters, key=lambda c: -c[2]):
        if not (.25*span < cx < .85*span and .25*span < cy < .85*span) or radius < 40:
            continue
        for a in np.linspace(0, 2*np.pi, 24, endpoint=False):
            px, py = cx+1.5*radius*np.cos(a), cy+1.5*radius*np.sin(a)
            if .08*span < px < .92*span and .08*span < py < .92*span and firm[cell(px, py)]:
                return [round(float(px), 1), round(float(py), 1)]
    # No crater to visit: the firm ground nearest the far corner.
    choices = np.argwhere(firm if firm.any() else largest)
    row, col = choices[np.argmin(np.hypot(choices[:, 0]-.85*(rows-1), choices[:, 1]-.85*(cols-1)))]
    return [float(col*terrain.dx), float(row*terrain.dy)]


def load_dem(source, row=0, col=0, size=160, vertical_factor=1.):
    """Read native-resolution crop; reject ambiguous or nonmetric horizontal coordinates."""
    import rasterio
    from rasterio.windows import Window
    with rasterio.open(source) as ds:
        tr = ds.transform
        if not ds.crs or not ds.crs.is_projected:
            raise ValueError('Use a projected lunar GeoTIFF with horizontal units in metres; geographic degrees require reprojection first.')
        if abs(ds.crs.linear_units_factor[1] - 1.) > 1e-6:
            raise ValueError('Horizontal projection units must be metres.')
        if tr.a <= 0 or tr.e >= 0 or abs(tr.b) > 1e-9 or abs(tr.d) > 1e-9:
            raise ValueError('Use a north-up GeoTIFF without rotation.')
        if row < 0 or col < 0 or row >= ds.height or col >= ds.width:
            raise ValueError('Crop origin is outside this DEM.')
        win = Window(col, row, min(size, ds.width-col), min(size, ds.height-row))
        data = ds.read(1, window=win, masked=True).astype(float).filled(np.nan)
        if min(data.shape) < 10:
            raise ValueError('Crop must contain at least 10 rows and columns.')
        data = (data * ds.scales[0] + ds.offsets[0]) * vertical_factor
        if not np.isfinite(data).any():
            raise ValueError('The selected crop contains no valid elevations.')
        if max((data.shape[1]-1)*tr.a, (data.shape[0]-1)*-tr.e) > 10000:
            raise ValueError('Select a region at most 10 km wide/high for the local flat-surface model.')
        # Row zero in the internal grid is south; original rasters start north.
        meta = {'crs': ds.crs.to_wkt(), 'crop_row': row, 'crop_column': col,
                'original_shape': [ds.height, ds.width], 'scale': ds.scales[0],
                'offset': ds.offsets[0], 'vertical_factor': vertical_factor,
                'southwest_pixel_center': list(ds.xy(row+data.shape[0]-1, col)),
                'transform': list(ds.window_transform(win))[:6]}
        return Terrain(np.flipud(data).copy(), tr.a, -tr.e, str(getattr(source, 'name', source)), meta)


def load_surround(source, terrain):
    """Read a coarser DEM of the same projection and place it in the crop's local metres."""
    import rasterio
    with rasterio.open(source) as ds:
        if ds.crs is None or not ds.crs.is_projected:
            raise ValueError('Surrounding terrain must use the same projected CRS as the crop.')
        data = ds.read(1, masked=True).astype(float).filled(np.nan)*ds.scales[0]+ds.offsets[0]
        sw_x, sw_y = ds.xy(ds.height-1, 0)
        origin = terrain.metadata['southwest_pixel_center']
        return Surround(np.flipud(data).copy(), ds.res[0], ds.res[1], sw_x-origin[0], sw_y-origin[1])


def hazards(terrain, slope_limit=12., roughness_limit=1.5, footprint=20.):
    z = terrain.z
    valid = np.isfinite(z)
    filled = np.where(valid, z, 0.)
    gy, gx = np.gradient(filled, terrain.dy, terrain.dx)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    # RMS departures from each neighbourhood's best-fitting plane.
    wy = max(3, int(np.ceil(footprint/terrain.dy)) | 1)
    wx = max(3, int(np.ceil(footprint/terrain.dx)) | 1)
    if wy > z.shape[0] or wx > z.shape[1]:
        return {'slope': slope, 'roughness': np.full_like(z, np.nan),
                'hazard': np.ones_like(z), 'safe': np.zeros_like(valid), 'known': np.zeros_like(valid)}
    from scipy.ndimage import correlate
    yy, xx = np.mgrid[-wy//2+1:wy//2+1, -wx//2+1:wx//2+1]
    xx, yy = xx * terrain.dx, yy * terrain.dy
    mean = uniform_filter(filled, size=(wy, wx), mode='nearest')
    variance = uniform_filter(filled**2, size=(wy, wx), mode='nearest') - mean**2
    mx = correlate(filled, xx/(wx*wy), mode='nearest')
    my = correlate(filled, yy/(wx*wy), mode='nearest')
    rough = np.sqrt(np.maximum(0, variance - mx**2/np.mean(xx**2) - my**2/np.mean(yy**2)))
    known = binary_erosion(valid, structure=np.ones((wy, wx)), border_value=0)
    score = np.clip(.65*slope/slope_limit + .35*rough/roughness_limit, 0, 1)
    surface_ok = valid & (slope <= slope_limit) & (rough <= roughness_limit)
    safe = known & binary_erosion(surface_ok, structure=np.ones((wy, wx)), border_value=0)
    score[~safe] = 1.
    return {'slope': slope, 'roughness': rough, 'hazard': score, 'safe': safe, 'known': known}
