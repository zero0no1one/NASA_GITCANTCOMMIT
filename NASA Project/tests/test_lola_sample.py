import unittest
from pathlib import Path
import numpy as np
from echo_path.terrain import load_dem, hazards
from echo_path.evaluation import evaluate

DATA = Path(__file__).resolve().parents[1] / 'data'
DEM = DATA / 'lola_site04_r2960_c400.tif'
SLOPE = DATA / 'lola_site04_r2960_c400_slope.tif'


class LolaSampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terrain = load_dem(str(DEM), size=240)

    def test_sample_loads_at_native_resolution(self):
        t = self.terrain
        self.assertEqual(t.z.shape, (240, 240))
        self.assertEqual((t.dx, t.dy), (5., 5.))
        self.assertTrue(np.isfinite(t.z).all())
        self.assertIn('stere', t.metadata['crs'].lower())

    def test_sample_has_eligible_landing_area(self):
        self.assertGreater(hazards(self.terrain, footprint=30.)['safe'].mean(), .2)

    def test_slope_matches_published_map(self):
        published = load_dem(str(SLOPE), size=240)
        diff = np.abs(hazards(self.terrain)['slope'] - published.z)[2:-2, 2:-2]
        self.assertLess(np.nanmax(diff), .05)

    def test_evaluation_runs_with_earth_at_grid_north(self):
        r = evaluate(self.terrain, earth_az=0.)
        self.assertTrue(r['nominal_feasible'])
        self.assertGreater(r['blocked_samples'], 0)
        self.assertIsNotNone(r['fallback'])


if __name__ == '__main__':
    unittest.main()
