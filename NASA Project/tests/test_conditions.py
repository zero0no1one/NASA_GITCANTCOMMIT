import json
import unittest
from pathlib import Path
import numpy as np
from echo_path.astro import direction
from echo_path.conditions import conditions, disc_visible, sky_position, windows
from echo_path.ephemeris import at, span
from echo_path.horizon import horizon_profile, skyline_at
from echo_path.terrain import MOON_RADIUS_M

CATALOG = {s['name']: s for s in json.loads((Path(__file__).resolve().parents[1]/'data'/'sites_catalog.json')
                                             .read_text(encoding='utf-8'))['sites']}


def site_year(name):
    s = CATALOG[name]
    return conditions(s['lat'], s['lon'], '2026-01-01T00:00', 365)['summary']


class EphemerisTests(unittest.TestCase):
    def test_table_covers_2026_to_2030(self):
        first, last = span()
        self.assertEqual(str(first), '2026-01-01T00:00:00')
        self.assertEqual(str(last), '2031-01-01T00:00:00')
        with self.assertRaises(ValueError):
            at(np.array(['2025-12-31T00:00'], 'datetime64[s]'))

    def test_sun_and_earth_stay_within_their_known_ranges(self):
        times = np.datetime64('2026-01-01T00:00')+np.arange(0, 5*365*24, 6).astype('timedelta64[h]')
        e = at(times)
        self.assertLess(np.abs(e['sun_lat']).max(), 1.6)            # the Moon's axis is tilted 1.54° to the ecliptic
        self.assertLess(np.abs(e['earth_lat']).max(), 7.)           # libration in latitude, about ±6.7°
        self.assertTrue(np.all((e['earth_lon'] < 9) | (e['earth_lon'] > 351)))   # libration in longitude, about ±7.9°
        self.assertTrue(356_000 < e['earth_distance_km'].min() and e['earth_distance_km'].max() < 407_000)

    def test_a_lunar_day_lasts_about_29_5_earth_days(self):
        times = np.datetime64('2026-01-01T00:00')+np.arange(0, 365*24).astype('timedelta64[h]')
        lon = np.unwrap(np.radians(at(times)['sun_lon']))
        days = 365/(abs(lon[-1]-lon[0])/(2*np.pi))
        self.assertAlmostEqual(days, 29.53, delta=.05)

    def test_values_between_hours_are_interpolated(self):
        e = at(np.array(['2026-01-01T00:00', '2026-01-01T00:30', '2026-01-01T01:00'], 'datetime64[s]'))
        self.assertAlmostEqual(e['sun_lat'][1], (e['sun_lat'][0]+e['sun_lat'][2])/2, places=6)


class GeometryTests(unittest.TestCase):
    def test_elevation_matches_the_existing_sky_model(self):
        cases = [(-85.45, 31.55, -6.5, 358.7, 221.2), (-89.46, -137.5, 1.2, 40., None), (.674, 23.47, .5, 100., None),
                 (26.1, 3.6, -1.3, 250., None), (-41.6, -154., 5., 2., 225.)]
        for lat, lon, blat, blon, d in cases:
            _, el = sky_position(lat, lon, blat, blon, d)
            self.assertAlmostEqual(float(el), direction(lat, lon, blat, blon, d)[1], places=6)

    def test_azimuth_is_a_true_compass_direction(self):
        self.assertAlmostEqual(float(sky_position(0., 0., 10., 0.)[0]), 0., places=6)      # due north
        self.assertAlmostEqual(float(sky_position(0., 0., 0., 10.)[0]), 90., places=6)     # due east
        self.assertAlmostEqual(float(sky_position(0., 0., -10., 0.)[0]), 180., places=6)
        self.assertAlmostEqual(float(sky_position(0., 0., 0., -10.)[0]), 270., places=6)

    def test_horizon_on_a_smooth_sphere_dips_by_the_expected_angle(self):
        eye = 2.
        profile = horizon_profile(-30., 40., eye, height_at=lambda la, lo: np.zeros(np.shape(la)))
        dip = -np.degrees(np.sqrt(2*eye/MOON_RADIUS_M))
        self.assertTrue(np.allclose(profile, dip, atol=.005))

    def test_disc_fraction_and_windows(self):
        self.assertAlmostEqual(float(disc_visible(1., 1., .27)), .5)
        self.assertEqual(float(disc_visible(2., 1., .27)), 1.)
        self.assertEqual(float(disc_visible(0., 1., .27)), 0.)
        self.assertEqual(windows(['a', 'b', 'c', 'd', 'e'], [True, True, False, True, False]), [['a', 'b'], ['d', 'd']])
        self.assertAlmostEqual(float(skyline_at(np.arange(360.), 359.5)), 179.5)   # wraps between 359° and 0°


class SiteConditionTests(unittest.TestCase):
    def test_near_side_sites_always_see_earth_and_the_far_side_never(self):
        for name in ('Apollo 11', 'Apollo 15', 'Chandrayaan-3 (Vikram)'):
            self.assertEqual(site_year(name)['earth_visible_pct'], 100., name)
        self.assertEqual(site_year("Chang'e 4")['earth_visible_pct'], 0.)

    def test_low_latitude_days_and_nights_each_last_about_two_weeks(self):
        s = site_year('Apollo 11')
        self.assertAlmostEqual(s['sunlit_pct'], 50., delta=2.)
        self.assertAlmostEqual(s['longest_dark_h'], 29.53*24/2, delta=20.)

    def test_south_pole_ridges_are_lit_most_of_the_year(self):
        # Published illumination studies put the best points on Connecting ridge and the peak near Shackleton
        # around 85-90% sunlit; low-latitude sites get half.
        self.assertGreater(site_year('Connecting ridge')['sunlit_pct'], 80.)
        self.assertGreater(site_year('Peak near Shackleton')['sunlit_pct'], 80.)
        self.assertLess(site_year('Connecting ridge')['longest_dark_h'], site_year('Apollo 11')['longest_dark_h'])

    def test_series_lines_up_with_the_summary(self):
        s = CATALOG['Leibnitz Beta plateau']
        c = conditions(s['lat'], s['lon'], '2027-03-01T00:00', 10, step_h=2.)
        self.assertEqual(len(c['times']), 10*12+1)
        self.assertEqual(c['times'][0], '2027-03-01T00:00:00Z')
        self.assertEqual(len(c['horizon']), 360)
        lit = np.asarray(c['sun']['visible']) >= .5
        self.assertAlmostEqual(c['summary']['sunlit_pct'], 100*lit.mean())
        self.assertEqual(sum(1 for _ in c['sunlight_windows']) > 0, lit.any())
        self.assertLessEqual(float(np.max(c['power_w'])), 1361*.3+1e-6)


if __name__ == '__main__':
    unittest.main()
