import type { TerrainGrid } from '../api'
import { formatPlace, groundVerdict, sampleField } from '../coords'
import { useSim } from '../state'

/** The large live coordinate: wherever the cursor is, otherwise the selected spot. */
export function Readout({ grid }: { grid: TerrainGrid }) {
  const hover = useSim((s) => s.hover)
  const pin = useSim((s) => s.pin)
  const target = useSim((s) => s.target)
  const terrainId = useSim((s) => s.terrainId)
  const spot = hover ?? pin ?? target
  // A spot on a map that's still loading can't be read against the grid of the previous one.
  if (!spot || grid.id !== terrainId) return <div className="readout" aria-hidden="true" />
  const [north, east] = formatPlace(grid, spot[0], spot[1])
  const z = sampleField(grid, 'z', spot[0], spot[1])
  const slope = sampleField(grid, 'slope', spot[0], spot[1])
  const verdict = groundVerdict(grid, spot[0], spot[1])
  return (
    <div className="readout">
      <p className="readout-place">
        <span>{north}</span> <span>{east}</span>
      </p>
      <p className="readout-ground">
        <span className={verdict.ok ? 'go' : 'warn'}>{verdict.text}</span>
        {z !== null && <span>{Math.round(z).toLocaleString('en-US')} m elevation</span>}
        {slope !== null && <span>{slope.toFixed(1)}° slope</span>}
      </p>
    </div>
  )
}
