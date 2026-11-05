import type { FlownRoute, Mission, RoverTimeline, Vec3 } from './api'

/** Index i and fraction f such that time lies between t[i] and t[i + 1]. */
export function locate(t: number[], time: number): [number, number] {
  if (time <= t[0]) return [0, 0]
  const last = t.length - 1
  if (time >= t[last]) return [Math.max(last - 1, 0), last > 0 ? 1 : 0]
  let lo = 0
  let hi = last
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (t[mid] <= time) lo = mid
    else hi = mid
  }
  return [lo, (time - t[lo]) / (t[hi] - t[lo])]
}

const mix = (a: number, b: number, f: number) => a + (b - a) * f
const mix3 = (a: Vec3, b: Vec3, f: number): Vec3 => [mix(a[0], b[0], f), mix(a[1], b[1], f), mix(a[2], b[2], f)]

export interface LanderTrack {
  t: number[]
  p: Vec3[]
  v: Vec3[]
  m: number[]
  thrust: number[]
  link: number[]
  landing: number
}

/** A later route replacing everything from its start time onward. */
export interface Divert extends FlownRoute {
  start: number
}

function splice(track: LanderTrack, route: FlownRoute, start: number): LanderTrack {
  const keep = track.t.filter((time) => time < start).length
  const t = [...track.t.slice(0, keep), ...route.time_s.map((time) => start + time)]
  return {
    t,
    p: [...track.p.slice(0, keep), ...route.path],
    v: [...track.v.slice(0, keep), ...route.velocity],
    m: [...track.m.slice(0, keep), ...route.mass_kg],
    thrust: [...track.thrust.slice(0, keep), ...route.thrust_n],
    link: [...track.link.slice(0, keep), ...route.link],
    landing: t[t.length - 1],
  }
}

/** The flight as planned: nominal descent, then any backup chosen for the outage, then any manual divert. */
export function landerTrack(mission: Mission, rank: number, divert: Divert | null): LanderTrack {
  const { nominal, outage, fallbacks } = mission
  let track: LanderTrack = {
    t: nominal.time_s, p: nominal.path, v: nominal.velocity, m: nominal.mass_kg, thrust: nominal.thrust_n, link: nominal.link,
    landing: nominal.time_s[nominal.time_s.length - 1],
  }
  const backup = fallbacks.find((f) => f.rank === rank)
  if (backup) track = splice(track, backup, outage.time_s)
  if (divert) track = splice(track, divert, divert.start)
  return track
}

export interface FlightState {
  position: Vec3
  velocity: Vec3
  mass: number
  thrust: number
  link: number
  /** Thrust direction per unit mass, for pointing the vehicle: acceleration plus lunar gravity. */
  accel: Vec3
}

const LUNAR_G = 1.62

export function sampleFlight(track: LanderTrack, time: number): FlightState {
  const [i, f] = locate(track.t, time)
  const j = Math.min(i + 1, track.t.length - 1)
  const dt = Math.max(track.t[j] - track.t[i], 1e-3)
  return {
    position: mix3(track.p[i], track.p[j], f),
    velocity: mix3(track.v[i], track.v[j], f),
    mass: mix(track.m[i], track.m[j], f),
    thrust: mix(track.thrust[i], track.thrust[j], f),
    link: track.link[f < 0.5 ? i : j],
    accel: [
      (track.v[j][0] - track.v[i][0]) / dt,
      (track.v[j][1] - track.v[i][1]) / dt,
      (track.v[j][2] - track.v[i][2]) / dt + LUNAR_G,
    ],
  }
}

export interface RoverState {
  x: number
  y: number
  z: number
  heading: number
  pitch: number
  speed: number
  comms: number
  sunlit: boolean
  battery: number
  done: boolean
}

export function sampleRover(tl: RoverTimeline, time: number): RoverState {
  const [i, f] = locate(tl.t, time)
  const j = Math.min(i + 1, tl.t.length - 1)
  const near = f < 0.5 ? i : j
  const done = time >= tl.t[tl.t.length - 1]
  return {
    x: mix(tl.x[i], tl.x[j], f),
    y: mix(tl.y[i], tl.y[j], f),
    z: mix(tl.z[i], tl.z[j], f),
    heading: tl.heading_deg[i],
    pitch: tl.pitch_deg[i],
    speed: done ? 0 : mix(tl.speed_m_s[i], tl.speed_m_s[j], f),
    comms: tl.comms[near],
    sunlit: tl.sunlit[near],
    battery: mix(tl.battery_pct[i], tl.battery_pct[j], f),
    done,
  }
}

export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const pad = (n: number) => String(n).padStart(2, '0')
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${pad(m)}:${pad(s % 60)}`
}
