import type { Mission, RoverTimeline, Vec3 } from './api'

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

export interface LanderTrack {
  t: number[]
  p: Vec3[]
  outageTime: number
}

/** Nominal descent until the outage, then the chosen fallback (rank 0 keeps the nominal route). */
export function landerTrack(mission: Mission, rank: number): LanderTrack {
  const { nominal, outage, fallbacks } = mission
  const fallback = fallbacks.find((f) => f.rank === rank)
  if (!fallback) return { t: nominal.time_s, p: nominal.path, outageTime: outage.time_s }
  const t: number[] = []
  const p: Vec3[] = []
  nominal.time_s.forEach((time, i) => {
    if (time < outage.time_s) {
      t.push(time)
      p.push(nominal.path[i])
    }
  })
  fallback.time_s.forEach((time, i) => {
    t.push(outage.time_s + time)
    p.push(fallback.path[i])
  })
  return { t, p, outageTime: outage.time_s }
}

export function samplePath(track: { t: number[]; p: Vec3[] }, time: number): Vec3 {
  const [i, f] = locate(track.t, time)
  const a = track.p[i]
  const b = track.p[Math.min(i + 1, track.p.length - 1)]
  return [mix(a[0], b[0], f), mix(a[1], b[1], f), mix(a[2], b[2], f)]
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
  return {
    x: mix(tl.x[i], tl.x[j], f),
    y: mix(tl.y[i], tl.y[j], f),
    z: mix(tl.z[i], tl.z[j], f),
    heading: tl.heading_deg[i],
    pitch: tl.pitch_deg[i],
    speed: time >= tl.t[tl.t.length - 1] ? 0 : mix(tl.speed_m_s[i], tl.speed_m_s[j], f),
    comms: tl.comms[near],
    sunlit: tl.sunlit[near],
    battery: mix(tl.battery_pct[i], tl.battery_pct[j], f),
    done: time >= tl.t[tl.t.length - 1],
  }
}

export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const pad = (n: number) => String(n).padStart(2, '0')
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${pad(m)}:${pad(s % 60)}`
}
