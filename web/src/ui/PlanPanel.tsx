import type { LandingSite, Mission } from '../api'
import { formatPlace } from '../coords'
import { restartRun, useSim, useSimInputs } from '../state'
import { formatClock } from '../track'

function SiteRow({ site, rank, mission, chosen, onChoose }: {
  site: LandingSite; rank: number; mission: Mission; chosen: boolean; onChoose: () => void
}) {
  const [north, east] = formatPlace(mission.terrain, site.x_m, site.y_m)
  const sky = site.earth_visible && site.sunlit ? 'Earth in view, sunlit'
    : site.earth_visible ? 'Earth in view, in shadow'
    : site.sunlit ? 'Sunlit, no view of Earth' : 'In shadow, no view of Earth'
  return (
    <li>
      <button type="button" className={`site${chosen ? ' chosen' : ''}`} aria-pressed={chosen} onClick={onChoose}>
        <span className="site-rank">{rank}</span>
        <span className="site-body">
          <span className="site-place">{north} {east}</span>
          <span className="site-facts">{site.slope_deg.toFixed(1)}° slope, {Math.round(site.fuel_remaining_kg)} kg fuel left</span>
          <span className="site-facts">{sky}</span>
        </span>
      </button>
    </li>
  )
}

/** Before flight: where the terrain says to land, and what happens if contact is lost on the way. */
export function PlanPanel({ mission, onChooseSite }: { mission: Mission; onChooseSite: (site: LandingSite) => void }) {
  const { sites, target, touchdownRank, outageStep, set } = useSimInputs()
  const { nominal, target: spot, comms, outage, fallbacks, has_dropout: hasDropout } = mission
  const flyable = nominal.feasible
  const chosen = (s: LandingSite) => target !== null && Math.hypot(target[0] - s.x_m, target[1] - s.y_m) < 1

  return (
    <section className="panel" aria-label="Plan the landing">
      <h2>Where to land</h2>
      <p className="lead">Ranked by how flat and smooth the ground is and the fuel to reach it. Choose one, or click anywhere on the Moon.</p>
      <ol className="sites">
        {sites.map((site, i) => (
          <SiteRow key={`${site.x_m},${site.y_m}`} site={site} rank={i + 1} mission={mission} chosen={chosen(site)} onChoose={() => onChooseSite(site)} />
        ))}
      </ol>
      {sites.length === 0 && <p className="note warn">No site on this map passes the landing limits. Click the Moon to pick a spot yourself.</p>}

      {!spot.eligible && (
        <p className="note warn">
          This target fails the landing limits ({spot.slope_deg.toFixed(1)}° slope). The lander can fly there, but it isn't a safe place to land.
        </p>
      )}
      {!flyable && (
        <p className="note warn">The lander can't reach this target: {nominal.reasons.join(', ').toLowerCase()}. Choose another spot.</p>
      )}
      <button type="button" className="primary" disabled={!flyable} onClick={() => useSim.setState({ playing: true })}>
        Begin descent
      </button>
      <p className="note">
        {hasDropout ? `Earth drops out of view at T+${formatClock(outage.time_s)} on this route.` : 'Earth stays in view for the whole descent.'}
      </p>

      <details className="fold">
        <summary>Plan for losing contact</summary>
        <label className="field">
          <span>Lose contact at</span>
          <select value={outageStep ?? outage.step} onChange={(e) => { set({ outageStep: Number(e.target.value) }); restartRun() }}>
            {comms.slice(0, -1).map((c) => (
              <option key={c.step} value={c.step}>
                T+{formatClock(c.time_s)}{c.state === 0 ? ', Earth hidden' : c.state === 1 ? ', Earth in view' : ', unknown'}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Then</span>
          <select value={touchdownRank} onChange={(e) => { set({ touchdownRank: Number(e.target.value) }); restartRun() }}>
            <option value={0}>Stay on this target</option>
            {fallbacks.map((f) => (
              <option key={f.rank} value={f.rank}>Divert to backup {f.rank}: {f.slope_deg.toFixed(1)}° slope, {Math.round(f.fuel_remaining_kg)} kg left</option>
            ))}
          </select>
        </label>
        {fallbacks.length === 0 && <p className="note warn">No backup is reachable from that moment.</p>}
      </details>
    </section>
  )
}
