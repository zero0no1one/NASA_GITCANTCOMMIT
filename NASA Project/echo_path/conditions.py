"""Sun and Earth over a lunar site through time: where they are, whether terrain hides them, and what that means
for solar power and direct-to-Earth communication.

Positions come from the JPL Horizons table (ephemeris.py) and the terrain skyline from horizon.py. Earth's position
includes parallax (it is only about 60 Moon radii away); the Sun's doesn't need it. A body counts as in view when the
centre of its disc is above the skyline, and the Sun's visible fraction allows for a partly hidden disc.

Power is for 1 m² of solar panel turned to face the Sun (the usual set-up near the pole, where the Sun stays low),
at 30% efficiency and 1361 W/m² sunlight: about 408 W in full sun. That is an illustrative assumption, not a spec.
"""
import numpy as np
from .ephemeris import at
from .horizon import cached_profile, skyline_at
from .terrain import MOON_RADIUS_M

SUN_RADIUS_DEG = .2666          # mean angular radius of the Sun seen from the Moon
EARTH_RADIUS_KM = 6371.
SOLAR_CONSTANT_W_M2 = 1361.
PANEL_EFFICIENCY = .30


def _unit(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    return np.stack([np.cos(la)*np.cos(lo), np.cos(la)*np.sin(lo), np.sin(la)], axis=-1)


def sky_position(site_lat, site_lon, body_lat, body_lon, distance_radii=None):
    """True-compass azimuth and elevation (degrees) of a body over (body_lat, body_lon), seen from the site."""
    site = _unit(site_lat, site_lon)
    body = _unit(body_lat, body_lon)
    if distance_radii is not None:
        body = body*np.asarray(distance_radii)[..., None]-site
        body /= np.linalg.norm(body, axis=-1, keepdims=True)
    la, lo = np.radians(site_lat), np.radians(site_lon)
    east = np.array([-np.sin(lo), np.cos(lo), 0.])
    north = np.array([-np.sin(la)*np.cos(lo), -np.sin(la)*np.sin(lo), np.cos(la)])
    up = site
    elevation = np.degrees(np.arcsin(np.clip(body@up, -1, 1)))
    azimuth = np.degrees(np.arctan2(body@east, body@north)) % 360
    return azimuth, elevation


def disc_visible(elevation, skyline, radius_deg):
    """Fraction of a body's disc above the skyline, treating the skyline as level across the disc."""
    x = np.clip((np.asarray(elevation)-skyline)/radius_deg, -1, 1)
    return (np.arccos(-x)+x*np.sqrt(1-x**2))/np.pi


def windows(times, flags):
    """Runs of consecutive True samples as [start, end] pairs (end is the last True sample)."""
    flags = np.asarray(flags, bool)
    edges = np.flatnonzero(np.diff(np.concatenate([[0], flags.astype(int), [0]])))
    return [[times[a], times[b-1]] for a, b in zip(edges[::2], edges[1::2])]


def _longest(flags, step_h):
    flags = np.asarray(flags, bool)
    if not flags.any():
        return 0.
    edges = np.flatnonzero(np.diff(np.concatenate([[0], flags.astype(int), [0]])))
    return float((edges[1::2]-edges[::2]).max()*step_h)


def conditions(lat, lon, start, days, step_h=1., eye_m=2.):
    """Everything the navigator shows for one site over one time span."""
    if not -90 <= lat <= 90:
        raise ValueError('Latitude must be between -90 and 90 degrees.')
    lon = ((lon+180) % 360)-180
    count = int(round(days*24/step_h))+1
    times = np.datetime64(start, 's')+(np.arange(count)*step_h*3600).astype('timedelta64[s]')
    ephem = at(times)
    profile = cached_profile(round(lat, 4), round(lon, 4), eye_m)

    sun_az, sun_el = sky_position(lat, lon, ephem['sun_lat'], ephem['sun_lon'])
    earth_radii = ephem['earth_distance_km']*1000/MOON_RADIUS_M
    earth_az, earth_el = sky_position(lat, lon, ephem['earth_lat'], ephem['earth_lon'], earth_radii)
    sun_frac = disc_visible(sun_el, skyline_at(profile, sun_az), SUN_RADIUS_DEG)
    earth_radius_deg = np.degrees(np.arcsin(EARTH_RADIUS_KM/ephem['earth_distance_km']))
    earth_frac = disc_visible(earth_el, skyline_at(profile, earth_az), earth_radius_deg)
    sunlit = sun_frac >= .5
    earth_up = earth_frac >= .5
    power = SOLAR_CONSTANT_W_M2*PANEL_EFFICIENCY*sun_frac
    stamps = [str(t)+'Z' for t in times]

    lit_el = sun_el[sunlit]
    return {
        'site': {'lat': lat, 'lon': lon, 'eye_m': eye_m},
        'times': stamps, 'step_h': step_h,
        'sun': {'azimuth': sun_az, 'elevation': sun_el, 'visible': sun_frac},
        'earth': {'azimuth': earth_az, 'elevation': earth_el, 'visible': earth_frac},
        'power_w': power,
        'horizon': profile,
        'sunlight_windows': windows(stamps, sunlit),
        'earth_windows': windows(stamps, earth_up),
        'summary': {
            'sunlit_pct': float(100*sunlit.mean()),
            'earth_visible_pct': float(100*earth_up.mean()),
            'both_pct': float(100*(sunlit & earth_up).mean()),
            'longest_dark_h': _longest(~sunlit, step_h),
            'longest_sunlit_h': _longest(sunlit, step_h),
            'longest_no_earth_h': _longest(~earth_up, step_h),
            'mean_sun_elevation_lit': float(lit_el.mean()) if len(lit_el) else None,
            'max_sun_elevation': float(sun_el.max()),
            'mean_power_w': float(power.mean()),
            'energy_kwh': float(power.sum()*step_h/1000),
        },
    }
