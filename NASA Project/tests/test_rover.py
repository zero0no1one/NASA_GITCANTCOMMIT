import json
import unittest
from pathlib import Path
import numpy as np
from echo_path.terrain import Terrain, load_dem
from echo_path.rover import Rover, traversability, astar, smooth, line_cost, drive, plan_rover

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
        cost = np.ones((10, 10))
        cost[2:8, 5] = np.inf
        path = astar(cost, (5, 0), (5, 9))
        corners = smooth(path, cost)
        self.assertLess(len(corners), len(path))
        self.assertEqual((corners[0], corners[-1]), (path[0], path[-1]))
        self.assertTrue(np.isfinite(sum(line_cost(cost, a, b) for a, b in zip(corners[:-1], corners[1:]))))

    def test_smoothing_never_costs_more_than_the_astar_route(self):
        # An expensive (not blocked) band with a cheap gap: a straight line would be shorter but costlier.
        cost = np.ones((60, 60))
        cost[:50, 30] = 500.
        path = astar(cost, (5, 5), (5, 55))
        self.assertGreaterEqual(max(r for r, _ in path), 50)
        corners = smooth(path, cost)
        self.assertLess(len(corners), len(path))
        self.assertGreaterEqual(max(r for r, _ in corners), 50)
        raw = sum(np.hypot(a[0]-b[0], a[1]-b[1])*(cost[a]+cost[b])/2 for a, b in zip(path[:-1], path[1:]))
        self.assertLessEqual(sum(line_cost(cost, a, b) for a, b in zip(corners[:-1], corners[1:])), raw+1e-9)

    def test_lola_route_keeps_the_shade_avoidance_astar_found(self):
        terrain = load_dem(str(LOLA), size=240)
        rover = Rover()
        grid = traversability(terrain, rover, 90., 5.)
        path = astar(grid['cost'], (120, 180), (200, 40), 5., 5.)
        straight, _, _ = drive(terrain, [path[0], path[-1]], grid, rover, 0., 3., 90., 5.)
        r = plan_rover(terrain, (900, 600), (200, 1000), rover, 0., 3., 90., 5., grid=grid)
        self.assertGreater(r['summary']['corners'], 2)
        self.assertLess(r['summary']['shadow_pct'], 100*np.diff(straight['t'])[~straight['sunlit'][:-1]].sum()/straight['t'][-1])

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

    def test_battery_saturates_at_full_instead_of_banking_charge(self):
        z = np.zeros((60, 60))
        z[:, 50:52] = 60.         # wall to the east shades the last part of the drive
        rover = Rover(solar_w=400., battery_wh=100.)
        tl = plan_rover(Terrain(z, 10., 10., 'wall'), (20, 300), (480, 300), rover, sun_az=90., sun_el=10.)['timeline']
        self.assertIn(True, tl['sunlit'])
        self.assertIn(False, tl['sunlit'])
        expected = 100.
        for i in range(len(tl['t'])-1):
            net = rover.drive_w+rover.idle_w-rover.solar_w*tl['sunlit'][i]
            expected = min(100., expected-net*(tl['t'][i+1]-tl['t'][i])/3600*100/rover.battery_wh)
        self.assertAlmostEqual(tl['battery_pct'][-1], expected, places=1)
        self.assertLessEqual(max(tl['battery_pct']), 100.)

    def test_rover_stops_when_the_battery_runs_out(self):
        r = plan_rover(self.flat, (50, 50), (550, 50), Rover(battery_wh=5), sun_az=90, sun_el=-5)
        self.assertFalse(r['feasible'])
        self.assertFalse(r['reached_goal'])
        self.assertIn('Battery depleted', r['reason'])
        tl = r['timeline']
        self.assertEqual(tl['battery_pct'][-1], 0.)
        self.assertGreater(min(tl['battery_pct'][:-1]), 0.)
        self.assertLess(tl['x'][-1], 200.)
        self.assertAlmostEqual(r['summary']['distance_m'], tl['x'][-1]-50, delta=1.)
        self.assertAlmostEqual(r['segments'][-1]['end_s'], tl['t'][-1], delta=.01)
        self.assertTrue(all(len(v) == len(tl['t']) for v in tl.values()))

    def test_empty_battery_stays_put_in_shadow_but_recovers_in_sun(self):
        dark = plan_rover(self.flat, (50, 50), (550, 50), Rover(start_battery_pct=0.), sun_az=90, sun_el=-5)
        self.assertEqual(len(dark['timeline']['t']), 1)
        self.assertEqual(dark['segments'], [])
        self.assertEqual(dark['summary']['duration_s'], 0.)
        json.dumps(dark)
        lit = plan_rover(self.flat, (50, 50), (550, 50), Rover(start_battery_pct=0.), sun_az=90, sun_el=10)
        self.assertTrue(lit['reached_goal'])
        self.assertGreater(lit['summary']['end_battery_pct'], 0.)

    def test_invalid_rover_settings_are_rejected(self):
        for bad in (Rover(speed=0.), Rover(speed=-1.), Rover(max_slope=0.), Rover(battery_wh=0.), Rover(min_speed_frac=0.)):
            with self.assertRaisesRegex(ValueError, 'must be positive'):
                plan_rover(self.flat, (50, 50), (550, 50), bad)

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
