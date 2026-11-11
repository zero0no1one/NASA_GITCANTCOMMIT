import type { ConditionsSummary } from '../../api'
import { formatHours } from './time'

interface Column {
  label: string
  value: (s: ConditionsSummary) => number
  show: (v: number) => string
  better: 'high' | 'low' | null
}

const pct = (v: number) => `${Math.round(v)}%`
const COLUMNS: Column[] = [
  { label: 'Sunlit', value: (s) => s.sunlit_pct, show: pct, better: 'high' },
  { label: 'Earth in view', value: (s) => s.earth_visible_pct, show: pct, better: 'high' },
  { label: 'Both', value: (s) => s.both_pct, show: pct, better: 'high' },
  { label: 'Longest night', value: (s) => s.longest_dark_h, show: formatHours, better: 'low' },
  { label: 'Longest without Earth', value: (s) => s.longest_no_earth_h, show: formatHours, better: 'low' },
  { label: 'Average solar power', value: (s) => s.mean_power_w, show: (v) => `${Math.round(v)} W`, better: 'high' },
  { label: 'Highest Sun', value: (s) => s.max_sun_elevation, show: (v) => `${v.toFixed(1)}°`, better: null },
]

/** Side by side over the same span; the best value in each column is highlighted. */
export function CompareTable({ rows, focus, onFocus }: {
  rows: { key: string; name: string; summary: ConditionsSummary | null }[]; focus: string; onFocus: (key: string) => void
}) {
  const ready = rows.filter((r) => r.summary) as { key: string; name: string; summary: ConditionsSummary }[]
  const best = COLUMNS.map((col) => {
    if (!col.better || ready.length < 2) return null
    const values = ready.map((r) => col.value(r.summary))
    return col.better === 'high' ? Math.max(...values) : Math.min(...values)
  })
  return (
    <div className="cmp-scroll">
      <table className="cmp-table">
        <thead>
          <tr><th scope="col">Site</th>{COLUMNS.map((c) => <th key={c.label} scope="col">{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className={r.key === focus ? 'focus' : ''}>
              <th scope="row"><button type="button" onClick={() => onFocus(r.key)}>{r.name}</button></th>
              {COLUMNS.map((col, i) => {
                if (!r.summary) return <td key={col.label}>…</td>
                const v = col.value(r.summary)
                return <td key={col.label} className={best[i] !== null && Math.abs(v - best[i]!) < 1e-9 ? 'best' : ''}>{col.show(v)}</td>
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
