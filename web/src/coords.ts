import type { TerrainGrid } from './api'

const MOON_RADIUS_M = 1737400

/** Latitude and longitude of a point on the local grid; null for terrain with no real location. */
export function latLon(grid: TerrainGrid, x: number, y: number): [number, number] | null {
  if (!grid.origin_xy) return null
  const px = grid.origin_xy[0] + x
  const py = grid.origin_xy[1] + y
  const lat = -90 + (2 * Math.atan(Math.hypot(px, py) / (2 * MOON_RADIUS_M)) * 180) / Math.PI
  return [lat, (Math.atan2(px, py) * 180) / Math.PI]
}

/** The local grid position of a latitude and longitude (south polar stereographic). */
export function toLocal(grid: TerrainGrid, lat: number, lon: number): [number, number] | null {
  if (!grid.origin_xy) return null
  const rho = 2 * MOON_RADIUS_M * Math.tan((((90 + lat) / 2) * Math.PI) / 180)
  const l = (lon * Math.PI) / 180
  return [rho * Math.sin(l) - grid.origin_xy[0], rho * Math.cos(l) - grid.origin_xy[1]]
}

export const formatLat = (lat: number) => `${Math.abs(lat).toFixed(4)}° ${lat < 0 ? 'S' : 'N'}`
export const formatLon = (lon: number) => `${Math.abs(lon).toFixed(4)}° ${lon < 0 ? 'W' : 'E'}`

/** Coordinates as display text: real latitude and longitude, or metres on test terrain. */
export function formatPlace(grid: TerrainGrid, x: number, y: number): [string, string] {
  const ll = latLon(grid, x, y)
  return ll ? [formatLat(ll[0]), formatLon(ll[1])] : [`${x.toFixed(0)} m east`, `${y.toFixed(0)} m north`]
}

type Field = 'z' | 'hazard' | 'slope' | 'roughness'

/** Bilinear value of a grid field at a point, or null outside the map or on missing data. */
export function sampleField(grid: TerrainGrid, field: Field, x: number, y: number): number | null {
  const fx = x / grid.dx
  const fy = y / grid.dy
  if (fx < 0 || fy < 0 || fx > grid.cols - 1 || fy > grid.rows - 1) return null
  const c = Math.min(Math.floor(fx), grid.cols - 2)
  const r = Math.min(Math.floor(fy), grid.rows - 2)
  const a = fx - c
  const b = fy - r
  const v = grid[field]
  const i = r * grid.cols + c
  const corners = [v[i], v[i + 1], v[i + grid.cols], v[i + grid.cols + 1]]
  if (corners.includes(grid.nodata)) return null
  return (corners[0] * (1 - a) + corners[1] * a) * (1 - b) + (corners[2] * (1 - a) + corners[3] * a) * b
}

export interface GroundVerdict {
  ok: boolean
  text: string
}

/** Plain-language reason a spot can or can't be landed on, from the same limits the engine uses. */
export function groundVerdict(grid: TerrainGrid, x: number, y: number): GroundVerdict {
  const hazard = sampleCell(grid, 'hazard', x, y)
  const slope = sampleCell(grid, 'slope', x, y)
  const rough = sampleCell(grid, 'roughness', x, y)
  if (hazard === null || slope === null) return { ok: false, text: 'No terrain data here' }
  if (hazard < 1) return { ok: true, text: 'Safe to land' }
  if (slope > grid.slope_limit) return { ok: false, text: `Too steep: ${slope.toFixed(1)}°, limit ${grid.slope_limit}°` }
  if (rough !== null && rough > grid.roughness_limit) return { ok: false, text: `Too rough: ${rough.toFixed(1)} m, limit ${grid.roughness_limit} m` }
  return { ok: false, text: 'Too close to steep ground or the map edge' }
}

function sampleCell(grid: TerrainGrid, field: Field, x: number, y: number): number | null {
  const c = Math.round(x / grid.dx)
  const r = Math.round(y / grid.dy)
  if (c < 0 || r < 0 || c >= grid.cols || r >= grid.rows) return null
  const value = grid[field][r * grid.cols + c]
  return value === grid.nodata ? null : value
}

/** Compass bearing in degrees from one grid point to another, clockwise from grid north. */
export const bearing = (dx: number, dy: number) => ((Math.atan2(dx, dy) * 180) / Math.PI + 360) % 360

export const compass = (deg: number) => ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][Math.round(deg / 45) % 8]
