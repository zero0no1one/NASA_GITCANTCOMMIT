"""Where the Sun and Earth can appear in the sky from a site near the lunar south pole.

A simple Moon-fixed geometry using the published extremes rather than a time-resolved
ephemeris: libration moves the sub-Earth point about +-6.7 deg in latitude and +-7.9 deg
in longitude, and the Sun's latitude on the Moon stays within +-1.54 deg.
Directions use the south polar stereographic grid (x = rho sin(lon), y = rho cos(lon)).
"""
from math import asin, atan, atan2, cos, degrees, hypot, radians, sin, sqrt, tan
from .terrain import MOON_RADIUS_M

LIBRATION_LAT = 6.7
LIBRATION_LON = 7.9
SUN_LAT = 1.54
EARTH_DISTANCE_RADII = 221.2     # mean Earth-Moon distance / Moon radius


def grid_to_lat_lon(x, y):
    return -90+degrees(2*atan(hypot(x, y)/(2*MOON_RADIUS_M))), degrees(atan2(x, y))


def _unit(lat, lon):
    la, lo = radians(lat), radians(lon)
    return cos(la)*cos(lo), cos(la)*sin(lo), sin(la)


def _to_grid(v):
    lat, lon = asin(max(-1, min(1, v[2]))), atan2(v[1], v[0])
    rho = 2*MOON_RADIUS_M*tan((radians(90)+lat)/2)
    return rho*sin(lon), rho*cos(lon)


def direction(site_lat, site_lon, sub_lat, sub_lon, distance_radii=None):
    """Grid azimuth and elevation (deg) of a body over (sub_lat, sub_lon); a finite distance adds parallax."""
    s = _unit(site_lat, site_lon)
    b = _unit(sub_lat, sub_lon)
    if distance_radii:
        b = tuple(distance_radii*c-d for c, d in zip(b, s))
        norm = sqrt(sum(c*c for c in b))
        b = tuple(c/norm for c in b)
    along = sum(c*d for c, d in zip(b, s))
    flat = tuple(c-along*d for c, d in zip(b, s))
    norm = sqrt(sum(c*c for c in flat)) or 1.
    q = tuple(d+1e-4*c/norm for c, d in zip(flat, s))
    norm = sqrt(sum(c*c for c in q))
    q = tuple(c/norm for c in q)
    x0, y0 = _to_grid(s)
    x1, y1 = _to_grid(q)
    return degrees(atan2(x1-x0, y1-y0)) % 360, degrees(asin(max(-1, min(1, along))))


def _spread(values):
    """Centre the range on the first value so azimuths near north do not wrap around 360."""
    centre = values[0]
    offsets = [(v-centre+180) % 360-180 for v in values]
    return centre+min(offsets), centre+max(offsets)


def sky_limits(site_lat, site_lon):
    """Ranges the Earth and Sun can take from this site, plus Earth's mean position."""
    mean_az, mean_el = direction(site_lat, site_lon, 0., 0., EARTH_DISTANCE_RADII)
    earth = [direction(site_lat, site_lon, i*LIBRATION_LAT/4, j*LIBRATION_LON/4, EARTH_DISTANCE_RADII)
             for i in range(-4, 5) for j in range(-4, 5)]
    az_low, az_high = _spread([mean_az]+[a for a, _ in earth])
    sun_el = [direction(site_lat, site_lon, lat, lon)[1] for lat in (-SUN_LAT, 0., SUN_LAT) for lon in range(0, 360, 5)]
    return {'earth': {'mean_az': mean_az, 'mean_el': mean_el, 'az_min': az_low, 'az_max': az_high,
                      'el_min': min(e for _, e in earth), 'el_max': max(e for _, e in earth)},
            'sun': {'el_min': min(sun_el), 'el_max': max(sun_el)}}


def site_of(terrain):
    """Latitude and longitude of the crop centre, from the metadata load_dem stores."""
    x, y = terrain.metadata['southwest_pixel_center']
    return grid_to_lat_lon(x+terrain.width/2, y+terrain.height/2)
