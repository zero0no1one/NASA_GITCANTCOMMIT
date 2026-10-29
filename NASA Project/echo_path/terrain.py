from dataclasses import dataclass, field
import numpy as np
from scipy.ndimage import map_coordinates, uniform_filter, binary_erosion


@dataclass
class Terrain:
    z: np.ndarray
    dx: float
    dy: float
    source: str
    metadata: dict = field(default_factory=dict)

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
