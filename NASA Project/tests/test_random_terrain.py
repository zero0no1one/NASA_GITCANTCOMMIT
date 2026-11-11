import unittest
import numpy as np
from echo_path.terrain import random_moon, hazards
from echo_path.rover import Rover, traversability


class RandomMoonTests(unittest.TestCase):
    def test_same_seed_same_surface_and_different_seeds_differ(self):
        a, b, c = random_moon(7), random_moon(7), random_moon(8)
        np.testing.assert_array_equal(a.z, b.z)
        self.assertEqual(a.metadata['goal_xy'], b.metadata['goal_xy'])
        self.assertGreater(np.abs(a.z-c.z).max(), 1.)

    def test_surface_is_a_complete_lunar_sized_patch(self):
        t = random_moon(3)
        self.assertEqual(t.z.shape, (121, 121))
        self.assertEqual((t.width, t.dx), (1200., 10.))
        self.assertTrue(np.isfinite(t.z).all())
        self.assertEqual(t.z.min(), 0.)
        self.assertIn('seed 3', t.source)

    def test_surfaces_vary_but_stay_landable(self):
        for seed in range(12):
            t = random_moon(seed)
            h = hazards(t, 12., 1.5, 30.)
            self.assertGreater(t.z.max()-t.z.min(), 20., seed)        # real relief, not a flat plain
            self.assertGreater((h['slope'] > 20).mean(), 0., seed)     # some ground too steep to land or drive on
            self.assertGreater(h['safe'].mean(), .05, seed)            # and somewhere safe to land

    def test_crater_walls_are_steep(self):
        t = random_moon(11)
        gy, gx = np.gradient(t.z, t.dy, t.dx)
        self.assertGreater(np.degrees(np.arctan(np.hypot(gx, gy))).max(), 15.)

    def test_goal_is_on_drivable_ground_inside_the_map(self):
        for seed in range(12):
            t = random_moon(seed)
            gx, gy = t.metadata['goal_xy']
            self.assertTrue(0 < gx < t.width and 0 < gy < t.height, seed)
            grid = traversability(t, Rover())
            row, col = int(round(gy/t.dy)), int(round(gx/t.dx))
            self.assertFalse(grid['blocked'][row, col], seed)


if __name__ == '__main__':
    unittest.main()
