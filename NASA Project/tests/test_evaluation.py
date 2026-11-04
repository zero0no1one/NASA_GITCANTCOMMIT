import json
import unittest
import numpy as np
from echo_path.terrain import Terrain, synthetic, hazards
from echo_path.evaluation import DEFAULTS, evaluate, format_markdown, slope_agreement, _windows


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = evaluate(synthetic())

    def test_nominal_lands_on_eligible_ground(self):
        n = self.result['nominal']
        self.assertTrue(self.result['nominal_feasible'])
        self.assertLess(n['hazard'], 1.)
        self.assertLessEqual(n['slope_deg'], DEFAULTS['slope'])

    def test_unmitigated_target_fails_surface_limits(self):
        u = self.result['unmitigated']
        self.assertIsNotNone(u)
        self.assertEqual(u['hazard'], 1.)
        self.assertTrue(u['slope_deg'] > DEFAULTS['slope'] or u['roughness_m'] > DEFAULTS['roughness'])

    def test_fallback_is_safe_and_within_fuel(self):
        f = self.result['fallback']
        self.assertIsNotNone(f)
        self.assertLess(f['hazard'], 1.)
        self.assertLessEqual(f['slope_deg'], DEFAULTS['slope'])
        self.assertGreaterEqual(f['fuel_margin_pct'], 0.)
        self.assertIsNotNone(self.result['outage_time_s'])

    def test_every_airborne_dropout_is_reported(self):
        coverage = self.result['coverage']
        self.assertGreater(len(coverage), 0)
        # Touchdown is the only blocked sample that cannot start a fallback.
        self.assertLessEqual(self.result['blocked_samples']-len(coverage), 1)
        for c in coverage:
            self.assertLessEqual(c['low_hazard_options'], c['options'])
        self.assertEqual(self.result['claim_three_low_hazard'], all(c['low_hazard_options'] >= 3 for c in coverage))

    def test_report_and_json_output(self):
        text = format_markdown(self.result)
        self.assertIn('| Landing hazard score (H) |', text)
        self.assertNotIn('insert', text)
        json.dumps(self.result)

    def test_blocked_windows_group_consecutive_samples(self):
        times = np.arange(6.)
        self.assertEqual(_windows(times, [0, 1, 1, 0, 1, 1]), [(1., 2.), (4., 5.)])
        self.assertEqual(_windows(times, [0]*6), [])

    def test_slope_agreement_is_zero_against_itself(self):
        h = hazards(synthetic())
        s = slope_agreement(h, Terrain(h['slope'].copy(), 10., 10., 'ref'))
        self.assertGreater(s['cells'], 0)
        self.assertAlmostEqual(s['max_abs_diff_deg'], 0., places=9)
        with self.assertRaisesRegex(ValueError, 'does not match'):
            slope_agreement({'slope': np.zeros((5, 5)), 'roughness': np.zeros((5, 5))}, Terrain(np.zeros((4, 4)), 1, 1, 'x'))


if __name__ == '__main__':
    unittest.main()
