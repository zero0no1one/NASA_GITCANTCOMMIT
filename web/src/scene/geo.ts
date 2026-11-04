import type { TerrainGrid } from '../api'

/**
 * Engine grid (x east, y north, z up, metres) to Three.js scene coordinates.
 * The terrain is centred on the origin; north is -Z and elevation is scaled by `exaggeration`.
 */
export function toScene(grid: TerrainGrid, exaggeration: number, x: number, y: number, z: number): [number, number, number] {
  const width = (grid.cols - 1) * grid.dx
  const height = (grid.rows - 1) * grid.dy
  return [x - width / 2, (z - grid.z_min) * exaggeration, -(y - height / 2)]
}

export function fromScene(grid: TerrainGrid, sx: number, sz: number): [number, number] {
  const width = (grid.cols - 1) * grid.dx
  const height = (grid.rows - 1) * grid.dy
  return [sx + width / 2, -sz + height / 2]
}

/** Unit vector pointing toward a direction given as azimuth (clockwise from grid north) and elevation. */
export function direction(azimuthDeg: number, elevationDeg: number): [number, number, number] {
  const az = (azimuthDeg * Math.PI) / 180
  const el = (elevationDeg * Math.PI) / 180
  return [Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el)]
}
