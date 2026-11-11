import type { MouseEvent } from 'react'
import type { Conditions } from '../../api'
import { runs } from './time'

export interface TimelineRow {
  key: string
  name: string
  c: Conditions | null
}

const W = 1000

/** When each site has sunlight and Earth in view across the span, on one shared clock. */
export function Timelines({ rows, times, cursor, focus, onSeek, onFocus }: {
  rows: TimelineRow[]; times: string[]; cursor: number; focus: string; onSeek: (i: number) => void; onFocus: (key: string) => void
}) {
  const n = times.length
  const at = (i: number) => (n > 1 ? (i / (n - 1)) * W : 0)
  const seek = (e: MouseEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect()
    onSeek(Math.round(((e.clientX - box.left) / box.width) * (n - 1)))
  }
  // A date label roughly every week, or every few days on short spans.
  const every = Math.max(1, Math.round(n / 6))
  const labels = times.map((t, i) => [i, t] as const).filter(([i]) => i % every === 0)

  return (
    <div className="timelines">
      {rows.map((row) => (
        <div key={row.key} className={`tl-row${row.key === focus ? ' focus' : ''}`}>
          <button type="button" className="tl-name" onClick={() => onFocus(row.key)}>{row.name}</button>
          {row.c ? (
            <svg className="tl" viewBox={`0 0 ${W} 26`} preserveAspectRatio="none" onClick={seek}
              role="img" aria-label={`${row.name}: sunlight and Earth-in-view periods`}>
              {runs(row.c.sun.visible).map(([a, b]) => <rect key={`s${a}`} className="tl-sun" x={at(a)} y={1} width={Math.max(at(b) - at(a), 1.5)} height={10} />)}
              {runs(row.c.earth.visible).map(([a, b]) => <rect key={`e${a}`} className="tl-earth" x={at(a)} y={14} width={Math.max(at(b) - at(a), 1.5)} height={10} />)}
              <line className="playhead" x1={at(cursor)} x2={at(cursor)} y1={0} y2={26} />
            </svg>
          ) : <p className="note tl-wait">Working it out…</p>}
        </div>
      ))}
      <div className="tl-row tl-axis-row">
        <span />
        <div className="tl-axis">
          {labels.map(([i, t]) => <span key={i} style={{ left: `${(at(i) / W) * 100}%` }}>{t.slice(5, 10)}</span>)}
        </div>
      </div>
      <p className="tl-key"><span className="key-sun">Sunlit</span> <span className="key-earth">Earth in view</span> Click a bar to jump there.</p>
    </div>
  )
}
