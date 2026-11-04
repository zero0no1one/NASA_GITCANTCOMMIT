// Types mirror the JSON returned by NASA Project/api/main.py.
// Grids are flattened row-major, row 0 at the south edge; x = col*dx, y = row*dy (metres).

export type Vec3 = [number, number, number]

export interface TerrainInfo {
  id: string
  label: string
  rows: number
  cols: number
  dx: number
  dy: number
  width_m: number
  height_m: number
  earth_az: number
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
}

export interface Fallback {
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
  path: Vec3[]
  time_s: number[]
}

export interface Mission {
  terrain: TerrainGrid
  eligible_pct: number
  earth: { azimuth_deg: number; elevation_deg: number }
  nominal: {
    feasible: boolean
    reasons: string[]
    fuel_used_kg: number
    peak_thrust_n: number
    path: Vec3[]
    time_s: number[]
    touchdown: Vec3
  }
  comms: { step: number; time_s: number; position: Vec3; state: number }[]
  outage: { step: number; time_s: number; position: Vec3 }
  fallbacks: Fallback[]
}

export interface MissionRequest {
  terrain: string
  earth_az?: number | null
  earth_el?: number
  outage_step?: number | null
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
  earth_el?: number
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
export const fetchMission = (req: MissionRequest) => call<Mission>('/api/mission', req)
export const fetchRover = (req: RoverRequest) => call<RoverPlan>('/api/rover', req)
