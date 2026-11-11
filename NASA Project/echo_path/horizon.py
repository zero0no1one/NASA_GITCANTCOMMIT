"""The terrain horizon around any point on the Moon: how high the land rises in each compass direction.

Heights come from NASA LOLA, finest first: 80 m patches 24 km across around each curated south-pole site, the
640 m south polar mosaic (poleward of about 80° S), and the global LDEM_4 map (4 pixels per degree, about 7.6 km). Both are heights above the 1,737.4 km
reference sphere in the Moon's mean-Earth/polar-axis frame. Rays follow great circles out to 400 km, and the angle
to each sample uses exact sphere geometry, so the Moon's curvature is included. With no atmosphere there is no
refraction to add.

Azimuths are true compass directions: 0° toward the north pole, 90° east, measured clockwise.
The maps limit accuracy. Away from the 80 m patches, ridges within a few kilometres are smoothed, which can put
the skyline a few degrees low. Outside the polar mosaic, features smaller than about 10 km don't show at all.
"""
from functools import lru_cache
from pathlib import Path
import numpy as np
from scipy.ndimage import map_coordinates
from .terrain import MOON_RADIUS_M

DATA = Path(__file__).resolve().parents[1]/'data'
GLOBAL_MAP = DATA/'ldem_4.img'        # 1440 x 720 little-endian int16, height = value * 0.5 m, row 0 at 90° N
POLAR_MAP = DATA/'lola_south_pole_surround_640m.tif'
SITE_PATCHES = DATA/'site_patches_80m.npz'   # built by data/make_site_patches.py
DISTANCES_M = np.geomspace(300., 400_000., 320)
AZIMUTHS = np.arange(360.)


@lru_cache(maxsize=1)
def _global():
    z = np.fromfile(GLOBAL_MAP, '<i2').reshape(720, 1440).astype(np.float32)*.5
    return np.pad(np.concatenate([z[:, -1:], z, z[:, :1]], axis=1), ((1, 1), (0, 0)), mode='edge')


@lru_cache(maxsize=1)
def _polar():
    import rasterio
    with rasterio.open(POLAR_MAP) as ds:
        z = ds.read(1, masked=True).astype(np.float32).filled(np.nan)*ds.scales[0]+ds.offsets[0]
        return z, ds.transform


@lru_cache(maxsize=1)
def _patches():
    """(sw_x, sw_y, spacing, heights with row 0 at the south) for each 80 m patch; heights NaN where unknown."""
    with np.load(SITE_PATCHES) as f:
        return [(float(x), float(y), float(d), np.where(z == -32768, np.nan, z).astype(np.float32))
                for (x, y, d), z in zip(f['origins'], f['z'])]


def _polar_xy(lat, lon):
    """South polar stereographic metres, the grid the polar map and Echo-Path's crops use."""
    rho = 2*MOON_RADIUS_M*np.tan(np.radians(90+lat)/2)
    return rho*np.sin(np.radians(lon)), rho*np.cos(np.radians(lon))


def height(lat, lon):
    """Terrain height (m) above the reference sphere, from the finest map that covers each point."""
    lat, lon = np.broadcast_arrays(np.asarray(lat, float), np.asarray(lon, float))
    rows = (90-lat)*4-.5+1                      # +1 for the padding row added above
    cols = (lon % 360)*4-.5+1                   # +1 for the wrapped column added on the left
    z = map_coordinates(_global(), [rows.ravel(), cols.ravel()], order=1, mode='nearest').reshape(lat.shape)
    south = lat < -79.5
    if south.any():
        polar, transform = _polar()
        x, y = _polar_xy(lat[south], lon[south])
        col, row = ~transform @ (x, y)
        fine = map_coordinates(polar, [np.asarray(row)-.5, np.asarray(col)-.5], order=1, mode='constant', cval=np.nan)
        best = np.where(np.isfinite(fine), fine, z[south])
        for sw_x, sw_y, step, patch in _patches():
            rows_p, cols_p = (y-sw_y)/step, (x-sw_x)/step
            inside = (rows_p >= 0) & (cols_p >= 0) & (rows_p <= patch.shape[0]-1) & (cols_p <= patch.shape[1]-1)
            if inside.any():
                sharp = map_coordinates(patch, [rows_p[inside], cols_p[inside]], order=1, mode='nearest')
                best[inside] = np.where(np.isfinite(sharp), sharp, best[inside])
        z[south] = best
    return z


def _destination(lat, lon, azimuth, distance):
    """Point reached by going `distance` metres along a great circle from (lat, lon) toward `azimuth`."""
    la, lo, az = np.radians(lat), np.radians(lon), np.radians(azimuth)
    d = distance/MOON_RADIUS_M
    la2 = np.arcsin(np.clip(np.sin(la)*np.cos(d)+np.cos(la)*np.sin(d)*np.cos(az), -1, 1))
    lo2 = lo+np.arctan2(np.sin(az)*np.sin(d)*np.cos(la), np.cos(d)-np.sin(la)*np.sin(la2))
    return np.degrees(la2), np.degrees(lo2)


def horizon_profile(lat, lon, eye_m=2., height_at=height):
    """Elevation angle (degrees) of the skyline in each whole-degree compass direction, seen from eye_m above the ground."""
    az, dist = np.meshgrid(AZIMUTHS, DISTANCES_M, indexing='ij')
    la, lo = _destination(lat, lon, az, dist)
    r0 = MOON_RADIUS_M+float(height_at(lat, lon))+eye_m
    r1 = MOON_RADIUS_M+height_at(la, lo)
    gamma = dist/MOON_RADIUS_M
    angle = np.degrees(np.arctan2(r1*np.cos(gamma)-r0, r1*np.sin(gamma)))
    return angle.max(axis=1)


@lru_cache(maxsize=64)
def cached_profile(lat, lon, eye_m=2.):
    """horizon_profile for a site rounded to about 10 m, so repeated requests reuse the work."""
    profile = horizon_profile(lat, lon, eye_m)
    profile.setflags(write=False)
    return profile


def skyline_at(profile, azimuth):
    """Skyline elevation in any direction, interpolated between whole degrees and wrapping at north."""
    return np.interp(np.asarray(azimuth) % 360, np.append(AZIMUTHS, 360.), np.append(profile, profile[0]))
