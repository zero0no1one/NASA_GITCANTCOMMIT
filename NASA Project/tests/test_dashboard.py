import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


class DashboardTests(unittest.TestCase):
    def test_demo_interactions_and_coverage_reset(self):
        at = AppTest.from_file(APP, default_timeout=60).run()
        self.assertFalse(at.exception, str(at.exception))
        self.assertFalse(at.error)
        self.assertEqual(len(at.tabs), 5)
        self.assertEqual(len(at.get('plotly_chart')), 2)
        at.button[0].click().run()
        self.assertFalse(at.exception, str(at.exception))
        self.assertGreater(len(at.session_state['coverage']), 0)
        self.assertTrue(all(r['options'] > 0 for r in at.session_state['coverage']))
        fuel = next(w for w in at.number_input if w.label == 'Initial propellant (kg)')
        fuel.set_value(1.).run()
        self.assertFalse(at.exception, str(at.exception))
        self.assertTrue(any('Insufficient fuel' in e.value for e in at.error))
        self.assertEqual(at.session_state['coverage'], [])
        self.assertTrue(at.button[0].disabled)

    def test_missing_dem_and_shadow_controls(self):
        at = AppTest.from_file(APP, default_timeout=60).run()
        next(w for w in at.checkbox if w.label == 'Require sunlit landing sites').check().run()
        self.assertFalse(at.exception, str(at.exception))
        next(w for w in at.slider if w.label == 'Sun elevation (degrees)').set_value(-5.).run()
        self.assertFalse(at.exception, str(at.exception))
        self.assertEqual(at.metric[0].value, '0.0%')
        at.selectbox[0].select('Local GeoTIFF path').run()
        self.assertFalse(at.exception, str(at.exception))
        self.assertTrue(at.info)
        at.text_input[0].set_value('C:/nonexistent-echo-path-test.tif')
        next(w for w in at.checkbox if 'confirm this is lunar' in w.label).check().run()
        self.assertFalse(at.exception, str(at.exception))
        self.assertTrue(any('could not be loaded' in e.value for e in at.error))


if __name__ == '__main__':
    unittest.main()
