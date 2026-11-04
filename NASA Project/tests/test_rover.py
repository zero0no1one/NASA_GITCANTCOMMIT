import json
import unittest
from pathlib import Path
import numpy as np
from echo_path.terrain import Terrain, load_dem
from echo_path.rover import Rover, traversability, astar, smooth, plan_rover

LOLA = Path(__file__).resolve().parents[1] / 'data' / 'lola_site04_r2960_c400.tif'


class RoverTests(unittest.TestCase):
    def setUp(self):
        self.flat = Terrain(np.zeros((60, 60)), 10., 10., 'flat')

    def test_flat_route_is_straight(self):
        r = plan_rover(self.flat, (100, 100), (500, 400))
        self.assertTrue(r['feasible'])
        self.assertEqual(r['summary']['corners'], 2)
        self.assertAlmostEqual(r['summary']['distance_m'], 500., delta=1.)
        self.assertAlmostEqual(r['segments'][0]['heading_deg'], np.degrees(np.arctan2(400, 300)), delta=.5)

    def test_route_detours_around_steep_wall(self):
        z = np.zeros((60, 60))
        z[:50, 30] = 50.          # a wall with a gap at the north end
        r = plan_rover(Terrain(z, 10., 10., 'wall'), (100, 100), (500, 100))
        self.assertTrue(r['feasible'], r.get('reason'))
        self.assertGreater(r['summary']['distance_m'], 600.)
        self.assertGreater(max(r['timeline']['y']), 450.)

    def test_unreachable_goal_reports_reason(self):
        z = np.zeros((60, 60))
        z[:, 30] = 50.
        r = plan_rover(Terrain(z, 10., 10., 'closed wall'), (100, 100), (500, 100))
        self.assertFalse(r['feasible'])
        self.assertIn('No traversable route', r['reason'])
        self.assertIn('outside', plan_rover(self.flat, (100, 100), (5000, 100))['reason'])

    def test_astar_matches_grid_optimum(self):
        cost = np.ones((5, 5))
        path = astar(cost, (0, 0), (4, 4))
        self.assertEqual(path, [(i, i) for i in range(5)])
        cost[2, :4] = np.inf
        self.assertEqual(astar(cost, (0, 0), (4, 0))[0], (0, 0))
        cost[2, 4] = np.inf
        self.assertIsNone(astar(cost, (0, 0), (4, 0)))

    def test_smoothing_keeps_route_off_blocked_cells(self):
        blocked = np.zeros((10, 10), bool)
        blocked[2:8, 5] = True
        path = astar(np.where(blocked, np.inf, 1.), (5, 0), (5, 9))
        corners = smooth(path, blocked)
        self.assertLess(len(corners), len(path))
        self.assertEqual((corners[0], corners[-1]), (path[0], path[-1]))

    def test_time_increases_and_slopes_slow_the_rover(self):
        y, x = np.mgrid[:60, :60]
        ramp = Terrain(np.where(x > 30, (x-30)*1.5, 0.), 10., 10., 'ramp')   # ~8.5 deg slope east of x=300 m
        r = plan_rover(ramp, (50, 300), (550, 300))
        t, v, xs = (np.array(r['timeline'][k]) for k in ('t', 'speed_m_s', 'x'))
        self.assertTrue(np.all(np.diff(t) > 0))
        self.assertLess(v[xs > 400].max(), v[xs < 250].min())

    def test_ridge_blocks_comms_along_the_drive(self):
        z = np.zeros((60, 60))
        z[:, 5:8] = 80.           # ridge to the west of the route
        r = plan_rover(Terrain(z, 10., 10., 'ridge'), (150, 100), (150, 500), earth_az=270, earth_el=3)
        self.assertEqual(r['summary']['comms_blocked_pct'], 100.)
        r = plan_rover(Terrain(z, 10., 10., 'ridge'), (150, 100), (150, 500), earth_az=90, earth_el=3)
        self.assertEqual(r['summary']['comms_blocked_pct'], 0.)

    def test_battery_drains_in_shadow_and_holds_in_sun(self):
        lit = plan_rover(self.flat, (50, 50), (550, 50), sun_az=90, sun_el=10)
        dark = plan_rover(self.flat, (50, 50), (550, 50), sun_az=90, sun_el=-5)
        self.assertEqual(lit['summary']['end_battery_pct'], 100.)
        self.assertEqual(dark['summary']['shadow_pct'], 100.)
        self.assertLess(dark['summary']['end_battery_pct'], 100.)
        tiny = plan_rover(self.flat, (50, 50), (550, 50), Rover(battery_wh=5), sun_az=90, sun_el=-5)
        self.assertFalse(tiny['feasible'])
        self.assertIn('Battery depleted', tiny['reason'])

    def test_lola_sample_produces_json_ready_route(self):
        terrain = load_dem(str(LOLA), size=240)
        grid = traversability(terrain, Rover(), 90., 5.)
        r = plan_rover(terrain, (900, 600), (200, 1000), earth_az=0., sun_az=90., sun_el=5., grid=grid)
        self.assertTrue(r['feasible'], r.get('reason'))
        json.dumps(r)
        n = len(r['timeline']['t'])
        self.assertTrue(all(len(v) == n for v in r['timeline'].values()))


if __name__ == '__main__':
    unittest.main()
