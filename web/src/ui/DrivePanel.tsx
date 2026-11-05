import { useMemo } from 'react'
import type { Mission } from '../api'
import { compass } from '../coords'
import { roverAt, useSim } from '../state'
import { formatClock } from '../track'

const W = 600
const H = 80
const LINK_LABEL: Record<number, [string, string]> = { 1: ['In contact', 'earth'], 0: ['Blocked', 'warn'], [-1]: ['Unknown', 'warn'] }

/** After touchdown: the rover's state, its route legs and how speed and battery change along the way. */
export function DrivePanel({ mission, landingEnd }: { mission: Mission; landingEnd: number }) {
  const simTime = useSim((s) => s.simTime)
  const plan = useSim((s) => s.plan)
  const planStart = useSim((s) => s.planStart)
  const history = useSim((s) => s.history)
  const replanning = useSim((s) => s.replanning)
  const roverError = useSim((s) => s.roverError)
  const tl = plan?.timeline

  const curves = useMemo(() => {
    if (!tl || tl.t.length < 2) return null
    const duration = tl.t[tl.t.length - 1] || 1
    const maxSpeed = Math.max(...tl.speed_m_s, 0.01)
    const x = (t: number) => (t / duration) * W
    const speed = tl.t.map((t, i) => `${x(t).toFixed(1)},${(H - (tl.speed_m_s[i] / maxSpeed) * (H - 6)).toFixed(1)}`).join(' ')
    const battery = tl.t.map((t, i) => `${x(t).toFixed(1)},${(H - (tl.battery_pct[i] / 100) * (H - 6)).toFixed(1)}`).join(' ')
    const shade = tl.t.slice(0, -1).map((t, i) => (tl.sunlit[i] ? null : (
      <rect key={i} x={x(t)} width={Math.max(x(tl.t[i + 1]) - x(t), 0.5)} y={0} height={H} className="shade-band" />
    )))
    return { duration, drawing: <>{shade}<polyline points={speed} className="line-speed" /><polyline points={battery} className="line-battery" /></> }
  }, [tl])

  const r = roverAt({ plan, planStart, history }, simTime)
  if (!r) {
    return (
      <section className="panel" aria-label="Rover">
        <h2>Touchdown</h2>
        <p className="note">{roverError ?? (replanning ? 'Planning the rover’s route…' : 'Click the Moon to send the rover somewhere.')}</p>
      </section>
    )
  }
  const [link, tone] = LINK_LABEL[r.comms] ?? LINK_LABEL[-1]
  const mapOnly = mission.terrain.sky.horizon_km === 0
  const title = !r.done ? 'Rover driving' : plan?.reached_goal === false ? 'Rover stopped: battery empty' : 'Rover at its goal'
  const head = curves ? (Math.min(Math.max(simTime - planStart, 0), curves.duration) / curves.duration) * W : 0

  return (
    <section className="panel" aria-label="Rover">
      <h2>{title}{replanning ? ', re-routing…' : ''}</h2>
      <p className="big-number">{r.speed.toFixed(2)} <small>m/s, heading {r.heading.toFixed(0)}° {compass(r.heading)}</small></p>
      <dl className="stats">
        <div><dt>Battery</dt><dd className={r.battery < 20 ? 'warn' : ''}>{r.battery.toFixed(0)}%</dd></div>
        <div><dt>Earth link</dt><dd className={tone}>{r.comms === 1 && mapOnly ? 'In contact (map only)' : link}</dd></div>
        <div><dt>Sunlight</dt><dd className={r.sunlit ? '' : 'warn'}>{!r.sunlit ? 'In shadow' : mapOnly ? 'Sunlit (map only)' : 'Sunlit'}</dd></div>
        <div><dt>Driving for</dt><dd>{formatClock(simTime - landingEnd)}</dd></div>
      </dl>
      <p className="note">Click the Moon to send the rover there. It turns from where it is now.</p>
      {roverError && <p className="note warn" role="status">{roverError}</p>}
      {curves && (
        <figure className="chart-box">
          <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="none" role="img" aria-label="Speed and battery along the route">
            {curves.drawing}
            <line x1={head} x2={head} y1={0} y2={H} className="playhead" />
          </svg>
          <figcaption><span className="key-speed">Speed</span> <span className="key-battery">Battery</span> <span className="key-shade">Shadow</span></figcaption>
        </figure>
      )}
      <p className="note route-key"><span className="earth">Blue route</span>: Earth in view. <span className="warn">Orange</span>: blocked.</p>
      {plan?.segments && plan.segments.length > 0 && (
        <details className="fold">
          <summary>Route legs and timing</summary>
          <table className="legs">
            <thead><tr><th>Start</th><th>Heading</th><th>Length</th><th>Speed</th></tr></thead>
            <tbody>
              {plan.segments.map((seg, i) => (
                <tr key={i} className={simTime - planStart >= seg.start_s && simTime - planStart < seg.end_s ? 'active' : ''}>
                  <td>T+{formatClock(planStart + seg.start_s)}</td>
                  <td>{seg.heading_deg.toFixed(0)}°</td>
                  <td>{seg.length_m.toFixed(0)} m</td>
                  <td>{seg.mean_speed_m_s.toFixed(2)} m/s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </section>
  )
}
