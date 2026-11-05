import tempfile
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.main import app, mount_web


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_check(self):
        self.assertEqual(self.client.get('/api/health').json(), {'status': 'ok'})

    def test_terrain_grids_are_compressed_cacheable_and_valid(self):
        r = self.client.get('/api/terrain/lola_site20', headers={'Accept-Encoding': 'gzip'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get('content-encoding'), 'gzip')
        self.assertIn('max-age', r.headers['cache-control'])
        self.assertEqual(r.headers['content-type'], 'application/json')
        t = r.json()                 # fails if the body was compressed twice
        self.assertEqual(len(t['z']), t['rows']*t['cols'])
        self.assertEqual(len(t['hazard']), len(t['z']))
        self.assertEqual(len(t['slope']), len(t['z']))
        self.assertEqual(t['sky']['horizon_km'], 186)
        plain = self.client.get('/api/terrain/lola_site20', headers={'Accept-Encoding': 'identity'})
        self.assertIsNone(plain.headers.get('content-encoding'))
        self.assertEqual(plain.json()['rows'], t['rows'])

    def test_terrain_carries_what_the_map_needs(self):
        t = self.client.get('/api/terrain/lola_site20').json()
        self.assertEqual(len(t['roughness']), len(t['z']))
        self.assertEqual(len(t['origin_xy']), 2)
        self.assertEqual(t['slope_limit'], 12.)
        self.assertIsNone(self.client.get('/api/terrain/synthetic').json()['origin_xy'])

    def test_horizon_layer_surrounds_the_crop(self):
        h = self.client.get('/api/terrain/lola_site20/horizon').json()
        self.assertEqual(len(h['z']), h['rows']*h['cols'])
        self.assertLessEqual(max(h['rows'], h['cols']), 201)
        self.assertLess(h['x0'], 0)
        self.assertGreater(h['x0']+(h['cols']-1)*h['dx'], 1195)
        self.assertEqual(self.client.get('/api/terrain/synthetic/horizon').json()['rows'], 0)
        self.assertEqual(self.client.get('/api/terrain/mars/horizon').status_code, 404)

    def test_landing_sites_are_ranked_spread_out_and_located(self):
        r = self.client.post('/api/sites', json={'terrain': 'lola_site20'}).json()
        sites = r['sites']
        self.assertGreaterEqual(len(sites), 3)
        self.assertLessEqual(len(sites), 5)
        self.assertEqual([s['score'] for s in sites], sorted(s['score'] for s in sites))
        for s in sites:
            self.assertLess(s['slope_deg'], 12.)
            self.assertAlmostEqual(s['lat'], -85.45, delta=.05)
            self.assertAlmostEqual(s['lon'], 31.55, delta=.5)
            self.assertGreater(s['fuel_remaining_kg'], 0.)
            self.assertIsInstance(s['earth_visible'], bool)
        for i, a in enumerate(sites):
            for b in sites[i+1:]:
                self.assertGreaterEqual(((a['x_m']-b['x_m'])**2+(a['y_m']-b['y_m'])**2)**.5, 90.)

    def test_sites_without_real_coordinates_say_so(self):
        s = self.client.post('/api/sites', json={'terrain': 'synthetic'}).json()['sites'][0]
        self.assertIsNone(s['lat'])

    def test_point_reports_ground_and_sky(self):
        safe = self.client.post('/api/point', json={'terrain': 'lola_site20', 'x': 475, 'y': 495}).json()
        self.assertTrue(safe['eligible'])
        self.assertLess(safe['hazard'], 1.)
        self.assertAlmostEqual(safe['lat'], -85.45, delta=.05)
        self.assertIsInstance(safe['earth_visible'], bool)
        edge = self.client.post('/api/point', json={'terrain': 'lola_site20', 'x': 0, 'y': 0}).json()
        self.assertFalse(edge['eligible'])
        self.assertEqual(self.client.post('/api/point', json={'terrain': 'lola_site20', 'x': 9e6, 'y': 0}).status_code, 422)

    def test_mission_flies_to_a_chosen_target(self):
        m = self.client.post('/api/mission', json={'terrain': 'lola_site20', 'target_xy': [475, 495]}).json()
        self.assertTrue(m['nominal']['feasible'])
        self.assertAlmostEqual(m['nominal']['touchdown'][0], 475, delta=.1)
        self.assertAlmostEqual(m['nominal']['touchdown'][1], 495, delta=.1)
        self.assertTrue(m['target']['eligible'])
        n = m['nominal']
        self.assertEqual(len(n['velocity']), len(n['path']))
        self.assertEqual(len(n['mass_kg']), len(n['path']))
        self.assertEqual(len(n['link']), len(n['path']))
        self.assertEqual(self.client.post('/api/mission', json={'target_xy': [1e7, 0]}).status_code, 422)

    def test_divert_replans_from_the_current_state(self):
        m = self.client.post('/api/mission', json={'terrain': 'lola_site20', 'target_xy': [900, 600]}).json()['nominal']
        i = 100
        body = {'terrain': 'lola_site20', 'position': m['path'][i], 'velocity': m['velocity'][i], 'mass': m['mass_kg'][i],
                'remaining_s': m['time_s'][-1]-m['time_s'][i], 'target': [475, 495]}
        d = self.client.post('/api/divert', json=body).json()
        self.assertTrue(d['feasible'], d['reasons'])
        self.assertEqual(d['path'][0], m['path'][i])
        self.assertAlmostEqual(d['touchdown'][0], 475, delta=.1)
        too_late = self.client.post('/api/divert', json={**body, 'remaining_s': 1., 'target': [10, 1190]}).json()
        self.assertFalse(too_late['feasible'])
        self.assertTrue(too_late['reasons'])
        self.assertEqual(self.client.post('/api/divert', json={**body, 'target': [9e6, 0]}).status_code, 422)

    def test_terrain_grid_inputs_are_checked(self):
        self.assertEqual(self.client.get('/api/terrain/mars').status_code, 404)
        self.assertEqual(self.client.get('/api/terrain/lola_site20?slope=0').status_code, 422)
        strict = self.client.get('/api/terrain/lola_site20?slope=5').json()
        self.assertGreater(sum(h == 1 for h in strict['hazard']),
                           sum(h == 1 for h in self.client.get('/api/terrain/lola_site20').json()['hazard']))

    def test_mission_leaves_grids_out_so_it_stays_small(self):
        r = self.client.post('/api/mission', json={'terrain': 'lola_site20'})
        self.assertLess(len(r.content), 100_000)
        self.assertEqual(r.json()['terrain_id'], 'lola_site20')
        self.assertNotIn('terrain', r.json())

    def test_built_web_app_is_served_alongside_the_api(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'index.html').write_text('<title>Echo-Path 3D</title>', encoding='utf-8')
            site = FastAPI()
            site.get('/api/health')(lambda: {'status': 'ok'})
            mount_web(site, folder)
            client = TestClient(site)
            self.assertIn('Echo-Path 3D', client.get('/').text)
            self.assertEqual(client.get('/api/health').json(), {'status': 'ok'})
        empty = FastAPI()
        mount_web(empty, Path(folder, 'missing'))
        self.assertEqual(TestClient(empty).get('/').status_code, 404)

    def test_terrains_report_real_sky_limits(self):
        r = self.client.get('/api/terrains')
        self.assertEqual(r.status_code, 200)
        ids = {t['id']: t for t in r.json()}
        self.assertEqual(set(ids), {'synthetic', 'lola_site04', 'lola_site20'})
        self.assertEqual(ids['lola_site20']['dx'], 5.)
        sky = ids['lola_site20']['sky']
        self.assertAlmostEqual(sky['lat'], -85.45, delta=.01)
        self.assertGreater(sky['earth_el'], 3.)            # Earth stays above the horizon on average here
        self.assertLess(sky['sun_el_max'], 6.5)
        self.assertLessEqual(sky['sun_el'], sky['sun_el_max'])
        self.assertGreater(sky['horizon_km'], 100)
        self.assertLess(ids['lola_site04']['sky']['earth_el'], 0.)   # but not this close to the pole
        self.assertEqual(ids['synthetic']['sky']['horizon_km'], 0.)

    def test_mission_defaults_to_the_site_sky_and_earth_drops_out_partway(self):
        m = self.client.post('/api/mission', json={'terrain': 'lola_site20'}).json()
        sky = self.client.get('/api/terrain/lola_site20').json()['sky']
        self.assertEqual(m['earth']['elevation_deg'], sky['earth_el'])
        states = [c['state'] for c in m['comms']]
        self.assertEqual(states[0], 1)
        self.assertIn(0, states)
        self.assertGreaterEqual(len(m['fallbacks']), 1)

    def test_rover_uses_site_sky_unless_told_otherwise(self):
        base = {'terrain': 'lola_site20', 'start': [900, 600], 'goal': [180, 1020]}
        r = self.client.post('/api/rover', json=base).json()
        self.assertTrue(r['feasible'], r.get('reason'))
        self.assertAlmostEqual(r['sun']['elevation_deg'], 4.9, delta=.05)
        self.assertGreater(r['summary']['comms_blocked_pct'], 0.)
        self.assertLess(r['summary']['comms_blocked_pct'], 100.)
        self.assertIsNone(self.client.post('/api/rover', json={**base, 'sun_el': None}).json()['sun'])

    def test_mission_returns_routes_and_comms(self):
        m = self.client.post('/api/mission', json={}).json()
        self.assertTrue(m['nominal']['feasible'])
        self.assertEqual(len(m['comms']), 31)
        self.assertEqual(m['comms'][m['outage']['step']]['state'], 0)
        self.assertGreaterEqual(len(m['fallbacks']), 1)
        self.assertEqual(m['fallbacks'][0]['path'][0], m['outage']['position'])

    def test_mission_outage_step_and_validation(self):
        m = self.client.post('/api/mission', json={'outage_step': 5}).json()
        self.assertEqual(m['outage']['step'], 5)
        self.assertEqual(self.client.post('/api/mission', json={'outage_step': 99}).status_code, 422)
        self.assertEqual(self.client.post('/api/mission', json={'terrain': 'mars'}).status_code, 404)

    def test_rover_handoff_from_lander_touchdown(self):
        m = self.client.post('/api/mission', json={'terrain': 'lola_site04'}).json()
        start = m['fallbacks'][0]['touchdown'][:2]
        r = self.client.post('/api/rover', json={'terrain': 'lola_site04', 'start': start, 'goal': [200, 1000]}).json()
        self.assertTrue(r['feasible'], r.get('reason'))
        self.assertAlmostEqual(r['timeline']['x'][0], round(start[0]/5)*5, delta=.01)
        for key in ('t', 'x', 'y', 'z', 'heading_deg', 'speed_m_s', 'comms', 'sunlit', 'battery_pct'):
            self.assertIn(key, r['timeline'])
        self.assertAlmostEqual(r['earth']['azimuth_deg'] % 360, 0., delta=.5)

    def test_rover_unreachable_goal_gives_reason(self):
        r = self.client.post('/api/rover', json={'start': [100, 500], 'goal': [5000, 500]}).json()
        self.assertFalse(r['feasible'])
        self.assertIn('outside', r['reason'])

    def test_invalid_rover_inputs_are_rejected_not_crashes(self):
        base = {'start': [700, 500], 'goal': [900, 900]}
        for bad in ({'speed': 0}, {'speed': -1}, {'max_slope': 0}, {'max_roughness': 0}, {'sun_el': 95},
                    {'sun_az': 400}, {'earth_el': -100}, {'start_battery_pct': 150}):
            self.assertEqual(self.client.post('/api/rover', json={**base, **bad}).status_code, 422, bad)

    def test_invalid_mission_inputs_are_rejected_not_crashes(self):
        for bad in ({'duration': 0}, {'isp': -5}, {'dry_mass': 0}, {'fuel': -1}, {'slope': 0},
                    {'start_pct': [200, 50]}, {'earth_az': 999}):
            self.assertEqual(self.client.post('/api/mission', json=bad).status_code, 422, bad)

    def test_rover_plans_without_sun_when_an_angle_is_missing(self):
        base = {'start': [700, 500], 'goal': [900, 900]}
        for missing in ({'sun_el': None}, {'sun_az': None}):
            r = self.client.post('/api/rover', json={**base, **missing})
            self.assertEqual(r.status_code, 200, missing)
            self.assertIsNone(r.json()['sun'])

    def test_rover_reports_when_it_runs_out_of_battery(self):
        r = self.client.post('/api/rover', json={'start': [700, 500], 'goal': [900, 900], 'sun_el': -5,
                                                 'start_battery_pct': 1}).json()
        self.assertFalse(r['reached_goal'])
        self.assertEqual(r['timeline']['battery_pct'][-1], 0.)


if __name__ == '__main__':
    unittest.main()
