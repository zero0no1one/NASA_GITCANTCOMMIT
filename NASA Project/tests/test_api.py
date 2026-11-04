import unittest
from fastapi.testclient import TestClient
from api.main import app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_terrains_lists_synthetic_and_lola(self):
        r = self.client.get('/api/terrains')
        self.assertEqual(r.status_code, 200)
        ids = {t['id']: t for t in r.json()}
        self.assertEqual(set(ids), {'synthetic', 'lola_site04'})
        self.assertEqual(ids['lola_site04']['dx'], 5.)
        self.assertEqual(ids['lola_site04']['earth_az'], 0.)

    def test_mission_returns_grid_routes_and_comms(self):
        m = self.client.post('/api/mission', json={}).json()
        t = m['terrain']
        self.assertEqual(len(t['z']), t['rows']*t['cols'])
        self.assertEqual(len(t['hazard']), len(t['z']))
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
        self.assertEqual(r['earth']['azimuth_deg'], 0.)

    def test_rover_unreachable_goal_gives_reason(self):
        r = self.client.post('/api/rover', json={'start': [100, 500], 'goal': [5000, 500]}).json()
        self.assertFalse(r['feasible'])
        self.assertIn('outside', r['reason'])


if __name__ == '__main__':
    unittest.main()
