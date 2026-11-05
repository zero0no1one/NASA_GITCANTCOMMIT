import unittest
from pathlib import Path
import numpy as np
from echo_path.terrain import Terrain, Surround, MOON_RADIUS_M, load_dem, load_surround, hazards
from echo_path.comms import visibility, shadow_map
from echo_path.astro import direction, grid_to_lat_lon, site_of, sky_limits, EARTH_DISTANCE_RADII
from echo_path.evaluation import evaluate

DATA = Path(__file__).resolve().parents[1] / 'data'
SITE20 = DATA / 'lola_site20_r1560_c1320.tif'
LAYERS = [DATA / 'lola_site20_surround_40m.tif', DATA / 'lola_south_pole_surround_640m.tif']


def ring(z, x0, y0, spacing=100.):
    return Surround(np.asarray(z, float), spacing, spacing, x0, y0)


class HorizonTests(unittest.TestCase):
    def setUp(self):
        self.flat = Terrain(np.zeros((21, 21)), 10., 10., 'flat')
        self.point = np.array([[100., 100., 1.5]])

    def far_wall(self, height, distance):
        """A surrounding layer with a wall across the north, `distance` metres from the crop."""
        rows = int((distance+5000)/100)
        z = np.zeros((rows, 21))
        z[int(distance/100):] = height
        return ring(z, -900., 0.)

    def test_terrain_beyond_the_crop_blocks_the_ray(self):
        self.assertEqual(visibility(self.flat, self.point, 0., 3.)[0], 1)
        self.flat.surroundings = [self.far_wall(500., 2000.)]
        self.assertEqual(visibility(self.flat, self.point, 0., 3.)[0], 0)
        self.assertEqual(visibility(self.flat, self.point, 0., 20.)[0], 1)
        self.assertEqual(visibility(self.flat, self.point, 180., 3.)[0], 1)

    def test_moon_curvature_lowers_distant_terrain(self):
        distance = 100000.
        drop = distance**2/(2*MOON_RADIUS_M)
        ray = .01*distance
        self.flat.surroundings = [self.far_wall(drop+ray-100., distance)]
        self.assertEqual(visibility(self.flat, self.point, 0., np.degrees(np.arctan(.01)))[0], 1)
        self.flat.surroundings = [self.far_wall(drop+ray+100., distance)]
        self.assertEqual(visibility(self.flat, self.point, 0., np.degrees(np.arctan(.01)))[0], 0)

    def test_coarse_layers_are_ignored_where_finer_data_exists(self):
        # A coarse layer spiking inside the crop must not overrule the crop's own flat ground.
        z = np.zeros((41, 41))
        z[20, 20] = 800.          # interpolates back to zero at the crop's edges
        self.flat.surroundings = [ring(z, -1900., -1900.)]
        self.assertEqual(visibility(self.flat, self.point, 0., 3.)[0], 1)

    def test_shadow_map_includes_distant_horizons(self):
        self.assertTrue((shadow_map(self.flat, 0., 3.) == 1).all())
        self.flat.surroundings = [self.far_wall(500., 2000.)]
        self.assertTrue((shadow_map(self.flat, 0., 3.) == 0).all())
        self.assertTrue((shadow_map(self.flat, 180., 3.) == 1).all())

    def test_surroundings_are_optional_for_visibility(self):
        self.flat.surroundings = [self.far_wall(500., 2000.)]
        self.assertEqual(visibility(self.flat, self.point, 0., 3., surroundings=False)[0], 1)


class SkyTests(unittest.TestCase):
    def test_grid_coordinates_match_a_known_location(self):
        lat, lon = grid_to_lat_lon(-6397.5, -14402.5)
        self.assertAlmostEqual(lat, -89.4803, places=3)
        self.assertAlmostEqual(lon, -156.0495, places=2)

    def test_directions_at_simple_geometries(self):
        az, el = direction(-85., 0., 0., 0.)
        self.assertAlmostEqual(el, 5., places=3)
        self.assertAlmostEqual(az % 360, 0., places=2)
        # Finite distance lowers a body by the parallax, about 0.26 deg for Earth.
        self.assertAlmostEqual(direction(-85., 0., 0., 0., EARTH_DISTANCE_RADII)[1], 5-.26, delta=.02)
        # On the far side of the pole the same body sits below the horizon.
        self.assertAlmostEqual(direction(-85., 180., 0., 0.)[1], -5., places=3)

    def test_sun_peak_follows_latitude(self):
        for lat in (-85., -89.5):
            self.assertAlmostEqual(sky_limits(lat, 0.)['sun']['el_max'], 90+lat+1.54, delta=.01)

    def test_earth_range_near_the_pole_includes_the_horizon(self):
        earth = sky_limits(-89.5, 0.)['earth']
        self.assertLess(earth['el_min'], 0.)
        self.assertGreater(earth['el_max'], 5.)
        self.assertLess(earth['el_max'], 8.)


class Site20Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terrain = load_dem(str(SITE20), size=240)
        cls.terrain.surroundings = [load_surround(str(p), cls.terrain) for p in LAYERS]
        cls.earth = sky_limits(*site_of(cls.terrain))['earth']

    def test_site_location_and_files(self):
        lat, lon = site_of(self.terrain)
        self.assertAlmostEqual(lat, -85.45, delta=.01)
        self.assertAlmostEqual(lon, 31.55, delta=.02)
        self.assertGreater(hazards(self.terrain, footprint=30.)['safe'].mean(), .5)

    def test_layers_line_up_with_the_crop(self):
        y, x = np.mgrid[10:231:20, 10:231:20]
        x, y = x*5., y*5.
        crop = self.terrain.sample(x, y)
        for layer, tolerance in zip(self.terrain.surroundings, (6., 40.)):
            self.assertLess(np.abs(layer.sample(x, y)-crop).mean(), tolerance)

    def test_earth_view_is_real_and_drops_out_during_descent(self):
        r = evaluate(self.terrain, earth_az=self.earth['mean_az'] % 360, earth_el=self.earth['mean_el'])
        self.assertTrue(r['nominal_feasible'])
        self.assertLess(r['blocked_samples'], r['total_samples'])
        self.assertGreater(r['blocked_samples'], 0)
        self.assertGreater(r['blocked_windows_s'][0][0], 60.)
        self.assertIsNotNone(r['fallback'])

    def test_far_terrain_changes_the_answer_somewhere(self):
        y, x = np.mgrid[0:240:20, 0:240:20]
        pts = np.column_stack((x.ravel()*5., y.ravel()*5.))
        pts = np.column_stack((pts, self.terrain.sample(pts[:, 0], pts[:, 1])+1.5))
        local = [visibility(self.terrain, pts, a, 1., surroundings=False) for a in range(0, 360, 45)]
        full = [visibility(self.terrain, pts, a, 1.) for a in range(0, 360, 45)]
        self.assertGreater(sum(int((a != b).sum()) for a, b in zip(local, full)), 0)


if __name__ == '__main__':
    unittest.main()
