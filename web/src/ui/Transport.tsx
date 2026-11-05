import { restartRun, useSim } from '../state'
import { formatClock } from '../track'

const RATES = [1, 5, 10, 50, 200]

/** The flight's timeline, with the moments that matter marked on it. */
export function Transport({ end, landingEnd, lostAt }: { end: number; landingEnd: number; lostAt: number | null }) {
  const simTime = useSim((s) => s.simTime)
  const playing = useSim((s) => s.playing)
  const rate = useSim((s) => s.rate)
  const set = useSim((s) => s.set)
  const finished = simTime >= end
  const mark = (t: number) => `${Math.min((t / Math.max(end, 1)) * 100, 100)}%`
  return (
    <div className="transport">
      <button type="button" className="secondary" onClick={() => set({ playing: finished ? playing : !playing })} disabled={finished}>
        {playing && !finished ? 'Pause' : 'Resume'}
      </button>
      <button type="button" className="quiet" onClick={restartRun}>Back to the plan</button>
      <div className="scrub">
        <input type="range" min={0} max={Math.max(end, 1)} step="any" value={simTime}
          onChange={(e) => set({ simTime: Number(e.target.value) })} aria-label="Mission time" />
        {lostAt !== null && <i className="tick tick-lost" style={{ left: mark(lostAt) }} title={`Earth lost at T+${formatClock(lostAt)}`} />}
        <i className="tick" style={{ left: mark(landingEnd) }} title={`Touchdown at T+${formatClock(landingEnd)}`} />
      </div>
      <output className="clock">T+{formatClock(simTime)}</output>
      <label className="rate">
        <span>Speed</span>
        <select value={rate} onChange={(e) => set({ rate: Number(e.target.value) })}>
          {RATES.map((r) => <option key={r} value={r}>{r}×</option>)}
        </select>
      </label>
    </div>
  )
}
