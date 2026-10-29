import unittest
import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from echo_path.terrain import Terrain, synthetic, hazards, load_dem
from echo_path.comms import visibility
from echo_path.trajectory import Vehicle, trajectory
from echo_path.routing import plan_fallbacks


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.flat = Terrain(np.zeros((101, 101)), 10., 10., 'test flat')
        self.vehicle = Vehicle()

    def test_planar_slope_and_detrended_roughness(self):
        y, x = np.mgrid[:51, :51]
        plane = Terrain(2*x+3*y+10., 10., 10., 'plane')
        h = hazards(plane, slope_limit=30.)
        self.assertAlmostEqual(h['slope'][25, 25], np.degrees(np.arctan(np.sqrt(.13))), places=7)
        self.assertLess(h['roughness'][25, 25], 1e-5)
        self.assertTrue(h['safe'][25, 25])
        self.assertFalse(h['safe'][0, 0])

    def test_flat_terrain_is_safe_and_missing_is_not(self):
        self.flat.z[50, 50] = np.nan
        h = hazards(self.flat)
        self.assertFalse(h['safe'][50, 50])
        self.assertFalse(h['safe'][49, 50])
        self.assertTrue(h['safe'][20, 20])

    def test_ridge_blocks_low_ray_but_not_high_ray(self):
        self.flat.z[:, 40:45] = 100
        points = np.array([[700, 500, 10], [700, 500, 150]])
        np.testing.assert_array_equal(visibility(self.flat, points, 270, 3), [0, 1])
        np.testing.assert_array_equal(visibility(self.flat, points, 270, -1), [0, 0])

    def test_missing_ray_is_unknown(self):
        self.flat.z[:, 40:45] = np.nan
        self.assertEqual(visibility(self.flat, [[700, 500, 10]], 270, 3)[0], -1)

    def test_hover_mass_matches_analytical_solution(self):
        r = trajectory(self.flat, [500, 500, 100], [0, 0, 0], [500, 500, 100], 60, 1000, self.vehicle)
        expected = 1000*np.exp(-1.62*60/(310*9.80665))
        self.assertAlmostEqual(r['mass'][-1], expected, places=8)
        self.assertTrue(r['feasible'])
        np.testing.assert_allclose(r['position'], np.tile([500, 500, 100], (len(r['t']), 1)))

    def test_fuel_and_thrust_rejections(self):
        low = Vehicle(fuel=1, max_thrust=100)
        r = trajectory(self.flat, [100, 500, 350], [4, 0, -3], [750, 500, 0], 120, 701, low)
        self.assertFalse(r['feasible'])
        self.assertIn('Insufficient fuel', r['reasons'])
        self.assertIn('Thrust limit exceeded', r['reasons'])

    def test_collision_and_outside_tile(self):
        self.flat.z[:, 40:60] = 500
        r = trajectory(self.flat, [100, 500, 100], [0, 0, 0], [900, 500, 0], 120, 1000, self.vehicle)
        self.assertIn('Terrain collision', r['reasons'])
        r = trajectory(self.flat, [100, 500, 100], [-50, 0, 0], [900, 500, 0], 120, 1000, self.vehicle)
        self.assertIn('Route leaves known terrain', r['reasons'])

    def test_demo_produces_continuous_feasible_fallbacks(self):
        terrain = synthetic()
        start = [150, 500, float(terrain.sample(150, 500))+350]
        end = [750, 500, float(terrain.sample(750, 500))]
        n = trajectory(terrain, start, [4, 0, -3], end, 120, 1000, self.vehicle)
        self.assertTrue(n['feasible'], n['reasons'])
        indices = np.linspace(0, len(n['t'])-1, 31).astype(int)
        states = visibility(terrain, n['position'][indices], 270, 3)
        self.assertTrue((states == 0).any())
        index = int(indices[np.flatnonzero(states == 0)[0]])
        options, _ = plan_fallbacks(terrain, hazards(terrain), n, index, self.vehicle)
        self.assertGreaterEqual(len(options), 1)
        for option in options:
            r = option['route']
            self.assertTrue(r['feasible'])
            np.testing.assert_allclose(r['position'][0], n['position'][index])
            np.testing.assert_allclose(r['velocity'][0], n['velocity'][index])
            self.assertAlmostEqual(r['mass'][0], n['mass'][index])
            np.testing.assert_allclose(r['velocity'][-1], 0, atol=1e-10)
            self.assertGreaterEqual(r['mass'][-1], self.vehicle.dry_mass)
        options, _ = plan_fallbacks(terrain, hazards(terrain), n, len(n['t'])-1, self.vehicle)
        self.assertEqual(options, [])

    def test_geotiff_units_orientation_scale_and_nodata(self):
        crs = '+proj=eqc +R=1737400 +units=m +no_defs'
        data = np.arange(400, dtype=np.float32).reshape(20, 20)
        data[0, 0] = -9999
        with MemoryFile() as mem:
            with mem.open(driver='GTiff', width=20, height=20, count=1, dtype='float32', crs=crs,
                          transform=from_origin(100, 400, 10, 20), nodata=-9999) as ds:
                ds.write(data, 1)
                ds.scales = [2.]
                ds.offsets = [5.]
            t = load_dem(mem.name, size=20)
        self.assertEqual(t.dx, 10)
        self.assertEqual(t.dy, 20)
        self.assertTrue(np.isnan(t.z[-1, 0]))
        self.assertEqual(t.z[0, 0], 380*2+5)
        self.assertEqual(t.metadata['southwest_pixel_center'], [105., 10.])

    def test_geographic_dem_rejected(self):
        with MemoryFile() as mem:
            with mem.open(driver='GTiff', width=20, height=20, count=1, dtype='float32', crs='EPSG:4326',
                          transform=from_origin(0, 1, .01, .01)) as ds:
                ds.write(np.zeros((20, 20), dtype=np.float32), 1)
            with self.assertRaisesRegex(ValueError, 'projected'):
                load_dem(mem.name)

    def test_export_archive_has_reproducible_state(self):
        import io
        import json
        import zipfile
        import pandas as pd
        from echo_path.export import export_bundle
        n = trajectory(self.flat, [100, 500, 350], [4, 0, -3], [750, 500, 0], 120, 1000, self.vehicle)
        h = hazards(self.flat)
        idx = len(n['t'])//2
        options, _ = plan_fallbacks(self.flat, h, n, idx, self.vehicle)
        payload = export_bundle(self.flat, h, n, {str(idx): options}, {'source': 'test'}, [])
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(json.loads(archive.read('mission.json'))['source'], 'test')
            nominal = pd.read_csv(io.BytesIO(archive.read('nominal.csv')))
            self.assertAlmostEqual(nominal['mass_kg'].iloc[-1], n['mass'][-1])
            route = pd.read_csv(io.BytesIO(archive.read(f'outage_{idx}/route_1.csv')))
            self.assertAlmostEqual(route['mass_kg'].iloc[0], n['mass'][idx])

    def test_footprint_larger_than_crop_excludes_all_sites(self):
        tiny = Terrain(np.zeros((10, 10)), .01, .01, 'tiny')
        self.assertFalse(hazards(tiny, footprint=100)['safe'].any())


if __name__ == '__main__':
    unittest.main()
