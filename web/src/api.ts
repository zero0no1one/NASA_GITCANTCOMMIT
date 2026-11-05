// Types mirror the JSON returned by NASA Project/api/main.py.
// Grids are flattened row-major, row 0 at the south edge; x = col*dx, y = row*dy (metres).

export type Vec3 = [number, number, number]

/** What the sky can really do at this terrain, and how far beyond the map horizons are known. */
export interface Sky {
  earth_az: number
  earth_el: number
  earth_el_min: number
  earth_el_max: number
  sun_az: number
  sun_el: number
  sun_el_min: number
  sun_el_max: number
  lat: number | null
  lon: number | null
  goal_xy: [number, number]
  horizon_km: number
}

export interface TerrainInfo {
  id: string
  label: string
  rows: number
  cols: number
  dx: number
  dy: number
  width_m: number
  height_m: number
  sky: Sky
}

export interface TerrainGrid {
  id: string
  source: string
  rows: number
  cols: number
  dx: number
  dy: number
  z_min: number
  z_max: number
  nodata: number
  z: number[]
  hazard: number[]
  slope: number[]
  roughness: number[]
  origin_xy: [number, number] | null
  slope_limit: number
  roughness_limit: number
  sky: Sky
}

export interface HorizonGrid {
  rows: number
  cols: number
  dx: number
  dy: number
  x0: number
  y0: number
  nodata: number
  z: number[]
}

export interface FlownRoute {
  path: Vec3[]
  time_s: number[]
  velocity: Vec3[]
  mass_kg: number[]
  thrust_n: number[]
  link: number[]      // line of sight to Earth at each sample: 1 clear, 0 blocked, -1 unknown
}

export interface CellReport {
  x_m: number
  y_m: number
  z_m: number
  hazard: number
  slope_deg: number
  roughness_m: number | null
  eligible: boolean
}

export interface Fallback extends FlownRoute {
  rank: number
  x_m: number
  y_m: number
  hazard: number
  slope_deg: number
  roughness_m: number
  fuel_used_kg: number
  fuel_remaining_kg: number
  duration_s: number
  score: number
  touchdown: Vec3
}

export interface Mission {
  terrain: TerrainGrid
  eligible_pct: number
  earth: { azimuth_deg: number; elevation_deg: number }
  target: CellReport
  has_dropout: boolean
  nominal: FlownRoute & {
    feasible: boolean
    reasons: string[]
    fuel_used_kg: number
    peak_thrust_n: number
    touchdown: Vec3
  }
  comms: { step: number; time_s: number; position: Vec3; state: number }[]
  outage: { step: number; time_s: number; position: Vec3 }
  fallbacks: Fallback[]
}

export interface MissionRequest {
  terrain: string
  target_xy?: [number, number] | null
  earth_az?: number | null
  earth_el?: number | null
  outage_step?: number | null
}

export interface LandingSite {
  x_m: number
  y_m: number
  z_m: number
  hazard: number
  slope_deg: number
  roughness_m: number
  fuel_used_kg: number
  fuel_remaining_kg: number
  lat: number | null
  lon: number | null
  earth_visible: boolean
  sunlit: boolean
  score: number
}

export interface SkyRequest {
  terrain: string
  earth_az?: number | null
  earth_el?: number | null
  sun_az?: number | null
  sun_el?: number | null
}

export interface PointReport extends CellReport {
  lat: number | null
  lon: number | null
  earth_visible: boolean
  sunlit: boolean
}

export interface Diverted extends Partial<FlownRoute> {
  feasible: boolean
  reasons: string[]
  target: CellReport
  touchdown?: Vec3
}

export interface RoverTimeline {
  t: number[]
  x: number[]
  y: number[]
  z: number[]
  heading_deg: number[]
  pitch_deg: number[]
  speed_m_s: number[]
  comms: number[]
  sunlit: boolean[]
  battery_pct: number[]
}

export interface RoverSegment {
  start_s: number
  end_s: number
  length_m: number
  heading_deg: number
  mean_speed_m_s: number
}

export interface RoverPlan {
  feasible: boolean
  reached_goal?: boolean
  reason: string | null
  summary?: {
    distance_m: number
    duration_s: number
    min_battery_pct: number
    end_battery_pct: number
    comms_blocked_pct: number
    shadow_pct: number
  }
  segments?: RoverSegment[]
  timeline?: RoverTimeline
}

export interface RoverRequest {
  terrain: string
  start: [number, number]
  goal: [number, number]
  earth_az?: number | null
  earth_el?: number | null
  sun_az?: number | null
  sun_el?: number | null
  max_slope?: number
  speed?: number
  start_battery_pct?: number
}

async function call<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, body === undefined ? undefined : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(typeof detail?.detail === 'string' ? detail.detail : `${path} failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

export const fetchTerrains = () => call<TerrainInfo[]>('/api/terrains')
export const fetchRover = (req: RoverRequest) => call<RoverPlan>('/api/rover', req)
export const fetchSites = (req: SkyRequest) => call<{ sites: LandingSite[] }>('/api/sites', req)
export const fetchPoint = (req: SkyRequest & { x: number; y: number }) => call<PointReport>('/api/point', req)
export const fetchDivert = (req: {
  terrain: string; position: Vec3; velocity: Vec3; mass: number; remaining_s: number; target: [number, number]; earth_az?: number; earth_el?: number
}) => call<Diverted>('/api/divert', req)

// Browsers cache terrain responses, so bump this whenever their contents change shape.
const TERRAIN_DATA_VERSION = 2

export const fetchHorizon = (id: string) => call<HorizonGrid>(`/api/terrain/${id}/horizon?v=${TERRAIN_DATA_VERSION}`)

// Terrain grids are most of the data and never change for a terrain, so each is fetched once.
const grids = new Map<string, Promise<TerrainGrid>>()

function fetchGrid(id: string): Promise<TerrainGrid> {
  let grid = grids.get(id)
  if (!grid) {
    grid = call<TerrainGrid>(`/api/terrain/${id}?v=${TERRAIN_DATA_VERSION}`)
    grids.set(id, grid)
    grid.catch(() => grids.delete(id))
  }
  return grid
}

export async function fetchMission(req: MissionRequest): Promise<Mission> {
  const [mission, terrain] = await Promise.all([call<Omit<Mission, 'terrain'>>('/api/mission', req), fetchGrid(req.terrain)])
  return { ...mission, terrain }
}
