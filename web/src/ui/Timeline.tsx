import { useMemo } from 'react'
import { restartRun, useSim } from '../state'
import { formatClock } from '../track'

const RATES = [1, 10, 20, 50, 200]
const W = 600
const H = 90

/** Playback controls, speed/battery chart for the current rover plan, and its timed route legs. */
export function Timeline({ end, landingEnd }: { end: number; landingEnd: number }) {
  const simTime = useSim((s) => s.simTime)
  const playing = useSim((s) => s.playing)
  const rate = useSim((s) => s.rate)
  const plan = useSim((s) => s.plan)
  const planStart = useSim((s) => s.planStart)
  const set = useSim((s) => s.set)
  const tl = plan?.timeline

  // The curves only change with the plan; only the playhead moves with the clock.
  const curves = useMemo(() => {
    if (!tl || tl.t.length < 2) return null
    const duration = tl.t[tl.t.length - 1] || 1
    const maxSpeed = Math.max(...tl.speed_m_s, 0.01)
    const x = (t: number) => (t / duration) * W
    const speed = tl.t.map((t, i) => `${x(t).toFixed(1)},${(H - (tl.speed_m_s[i] / maxSpeed) * (H - 8)).toFixed(1)}`).join(' ')
    const battery = tl.t.map((t, i) => `${x(t).toFixed(1)},${(H - (tl.battery_pct[i] / 100) * (H - 8)).toFixed(1)}`).join(' ')
    const shade = tl.t.slice(0, -1).map((t, i) => (tl.sunlit[i] ? null : (
      <rect key={i} x={x(t)} width={Math.max(x(tl.t[i + 1]) - x(t), 0.5)} y={0} height={H} className="shadow-band" />
    )))
    return {
      duration,
      drawing: (
        <>
          {shade}
          <polyline points={speed} className="line-speed" />
          <polyline points={battery} className="line-battery" />
        </>
      ),
    }
  }, [tl])

  let chart = null
  if (curves) {
    const head = (Math.min(Math.max(simTime - planStart, 0), curves.duration) / curves.duration) * W
    chart = (
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="none">
        {curves.drawing}
        <line x1={head} x2={head} y1={0} y2={H} className="playhead" />
      </svg>
    )
  }

  return (
    <div className="timeline">
      <div className="transport">
        <button onClick={() => set({ playing: !playing, ...(simTime >= end ? { simTime: 0 } : {}) })}>
          {playing && simTime < end ? 'Pause' : 'Play'}
        </button>
        <button onClick={restartRun}>Restart</button>
        <input type="range" min={0} max={Math.max(end, 1)} step="any" value={simTime}
          onChange={(e) => set({ simTime: Number(e.target.value) })} aria-label="Simulation time" />
        <span className="clock">T+{formatClock(simTime)} / {formatClock(end)}</span>
        <select value={rate} onChange={(e) => set({ rate: Number(e.target.value) })} aria-label="Playback speed">
          {RATES.map((r) => <option key={r} value={r}>×{r}</option>)}
        </select>
      </div>
      {chart && (
        <div className="chart-wrap">
          <div className="legend">
            <span className="k-speed">speed</span><span className="k-battery">battery</span><span className="k-shadow">shadow</span>
            <span className="muted">rover plan from T+{formatClock(planStart)} (landing T+{formatClock(landingEnd)})</span>
          </div>
          {chart}
        </div>
      )}
      {plan?.segments && plan.segments.length > 0 && (
        <table className="legs">
          <thead>
            <tr><th>Leg</th><th>Start</th><th>End</th><th>Heading</th><th>Length</th><th>Avg speed</th></tr>
          </thead>
          <tbody>
            {plan.segments.map((seg, i) => {
              const active = simTime - planStart >= seg.start_s && simTime - planStart < seg.end_s
              return (
                <tr key={i} className={active ? 'active' : ''}>
                  <td>{i + 1}</td>
                  <td>T+{formatClock(planStart + seg.start_s)}</td>
                  <td>T+{formatClock(planStart + seg.end_s)}</td>
                  <td>{seg.heading_deg.toFixed(0)}°</td>
                  <td>{seg.length_m.toFixed(0)} m</td>
                  <td>{seg.mean_speed_m_s.toFixed(2)} m/s</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
