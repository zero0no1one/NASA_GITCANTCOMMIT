import { useCallback } from 'react'
import { fetchDivert, type LandingSite } from './api'
import { phaseAt, useSim, useSimInputs, type CameraView, type Layer, type Phase } from './state'
import { sampleFlight } from './track'
import { usePlanner } from './usePlanner'
import { Scene } from './scene/Scene'
import { Readout } from './ui/Readout'
import { PlanPanel } from './ui/PlanPanel'
import { FlightPanel } from './ui/FlightPanel'
import { DrivePanel } from './ui/DrivePanel'
import { SettingsPanel, SpotPanel } from './ui/SpotPanel'
import { Transport } from './ui/Transport'

const LAYERS: [Layer, string][] = [['surface', 'Surface'], ['safety', 'Landing safety'], ['slope', 'Slope'], ['elevation', 'Height']]
const VIEWS: [CameraView, string][] = [['overview', 'Overview'], ['horizon', 'Horizon'], ['follow', 'Follow vehicle']]
const STEPS: [Phase, string][] = [['plan', 'Plan'], ['descent', 'Descend'], ['drive', 'Drive']]
const RANDOM_PREFIX = 'random-'

/** Go to another map: its own sky, sites and plan, starting from scratch. */
function switchTerrain(id: string) {
  useSim.setState({
    terrainId: id, earthAz: null, earthEl: null, missionEarthEl: null, sunAz: null, sunEl: null,
    outageStep: null, target: null, pin: null, sites: [], touchdownRank: 0,
  })
}

export default function App() {
  const { landingEnd, end, track } = usePlanner()
  const inputs = useSimInputs()
  const { mission, loading, missionError, terrains, terrainId, layer, view, set } = inputs
  const phase = useSim((s) => phaseAt(s.simTime, s.playing, mission ? landingEnd : Infinity))

  const chooseSite = useCallback((site: LandingSite) => {
    const place: [number, number] = [site.x_m, site.y_m]
    useSim.setState({ target: place, pin: place })
  }, [])

  const divertTo = useCallback(async (x: number, y: number) => {
    const now = useSim.getState()
    if (!now.mission || !track) return
    const remaining = track.landing - now.simTime
    if (remaining <= 0) return
    const state = sampleFlight(track, now.simTime)
    useSim.setState({ diverting: true, notice: null })
    try {
      const result = await fetchDivert({
        terrain: now.mission.terrain.id, position: state.position, velocity: state.velocity, mass: state.mass,
        remaining_s: remaining, target: [x, y], earth_az: now.mission.earth.azimuth_deg,
        earth_el: now.earthEl ?? now.mission.earth.elevation_deg,
      })
      if (result.feasible && result.path && result.time_s && result.velocity && result.mass_kg && result.thrust_n && result.link) {
        useSim.setState({
          divert: { path: result.path, time_s: result.time_s, velocity: result.velocity, mass_kg: result.mass_kg, thrust_n: result.thrust_n, link: result.link, start: now.simTime },
          divertTo: [x, y], diverting: false,
        })
      } else {
        useSim.setState({ diverting: false, notice: `The lander can’t reach that spot from here: ${result.reasons.join(', ').toLowerCase()}.` })
      }
    } catch (e) {
      useSim.setState({ diverting: false, notice: (e as Error).message })
    }
  }, [track])

  const act = useCallback((x: number, y: number) => {
    const place: [number, number] = [x, y]
    if (phase === 'plan') useSim.setState({ target: place })
    else if (phase === 'descent') void divertTo(x, y)
    else useSim.setState({ goal: place })
  }, [phase, divertTo])

  const clickGround = useCallback((x: number, y: number) => {
    const place: [number, number] = [x, y]
    // While driving, a click is a command: the rover should respond straight away.
    useSim.setState(phase === 'drive' ? { pin: place, goal: place } : { pin: place })
  }, [phase])

  const lostAt = track ? (() => {
    const i = track.link.findIndex((l) => l !== 1)
    return i >= 0 ? track.t[i] : null
  })() : null

  return (
    <div className="app">
      <div className="stage">
        {mission && track ? (
          <Scene mission={mission} track={track} end={end} landingEnd={landingEnd} phase={phase} onChooseSite={chooseSite} onClickGround={clickGround} />
        ) : (
          <p className="waking">{missionError ? '' : 'Loading lunar terrain. If the server has been idle, this can take about a minute.'}</p>
        )}
      </div>

      <header className="top">
        <div className="brand">
          <h1>Echo-Path</h1>
          <ol className="steps" aria-label="Mission phase">
            {STEPS.map(([id, label]) => <li key={id} className={id === phase ? 'now' : ''} aria-current={id === phase ? 'step' : undefined}>{label}</li>)}
          </ol>
        </div>
        {mission && <Readout grid={mission.terrain} />}
        <div className="view-tools">
          <div className="terrain-pick">
            <select aria-label="Terrain" value={terrainId} onChange={(e) => switchTerrain(e.target.value)}>
              {terrains.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
              {terrainId.startsWith(RANDOM_PREFIX) && (
                <option value={terrainId}>Random surface #{terrainId.slice(RANDOM_PREFIX.length)}</option>
              )}
            </select>
            <button type="button" className="secondary" onClick={() => switchTerrain(`${RANDOM_PREFIX}${Math.floor(Math.random() * 1e6)}`)}>
              New random surface
            </button>
          </div>
          <div className="seg" role="group" aria-label="Map layer">
            {LAYERS.map(([id, label]) => (
              <button key={id} type="button" aria-pressed={layer === id} onClick={() => set({ layer: id })}>{label}</button>
            ))}
          </div>
          <div className="seg" role="group" aria-label="Camera">
            {VIEWS.map(([id, label]) => (
              <button key={id} type="button" aria-pressed={view === id} onClick={() => set({ view: id, viewNonce: inputs.viewNonce + 1 })}>{label}</button>
            ))}
          </div>
          {layer === 'safety' && <p className="legend"><span className="ramp" /> Safest to too dangerous to land</p>}
        </div>
      </header>

      {mission && track && (
        <>
          <div className="rail left">
            {phase === 'plan' && <PlanPanel mission={mission} onChooseSite={chooseSite} />}
            {phase === 'descent' && <FlightPanel mission={mission} track={track} />}
            {phase === 'drive' && <DrivePanel mission={mission} landingEnd={landingEnd} />}
          </div>
          <div className="rail right">
            <SpotPanel mission={mission} phase={phase} onAct={act} />
            <SettingsPanel mission={mission} />
          </div>
          {phase !== 'plan' && <Transport end={end} landingEnd={landingEnd} lostAt={lostAt} />}
        </>
      )}

      <div className="alerts" role="status">
        {loading && mission && <p>Updating the plan…</p>}
        {missionError && (
          <p className="warn">
            Can’t reach the server: {missionError}. {import.meta.env.DEV ? 'Is the Python API running on port 8000?' : 'Reload the page in a moment.'}
          </p>
        )}
      </div>
    </div>
  )
}
