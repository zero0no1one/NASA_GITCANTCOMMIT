import { useCallback } from 'react'
import { fetchConditions, fetchDivert, type LandingSite, type TerrainInfo } from './api'
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
import { CompareView, type ChosenSite } from './ui/compare/CompareView'

const LAYERS: [Layer, string][] = [['surface', 'Surface'], ['safety', 'Landing safety'], ['slope', 'Slope'], ['elevation', 'Height']]
const VIEWS: [CameraView, string][] = [['overview', 'Overview'], ['horizon', 'Horizon'], ['follow', 'Follow vehicle']]
const STEPS: [Phase | 'compare', string][] = [['compare', 'Compare'], ['plan', 'Plan'], ['descent', 'Descend'], ['drive', 'Drive']]
const RANDOM_PREFIX = 'random-'
const MOON_RADIUS_KM = 1737.4
const NEARBY_KM = 25   // how close a site must be to a 3D landing map for "Simulate landing here"

function distanceKm(lat1: number, lon1: number, lat2: number, lon2: number) {
  const r = Math.PI / 180
  const a = Math.sin(((lat2 - lat1) * r) / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(((lon2 - lon1) * r) / 2) ** 2
  return 2 * MOON_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(a)))
}

/** The real-terrain 3D map closest to a site, if one is near enough to stand in for it. */
function nearestMap(terrains: TerrainInfo[], site: ChosenSite) {
  const maps = terrains.filter((t) => t.sky.lat !== null && t.sky.lon !== null)
    .map((t) => ({ t, km: distanceKm(site.lat, site.lon, t.sky.lat!, t.sky.lon!) }))
    .sort((a, b) => a.km - b.km)
  return maps[0] && maps[0].km <= NEARBY_KM ? maps[0] : null
}

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
  const { mission, loading, missionError, terrains, terrainId, layer, view, mode, set } = inputs
  const phase = useSim((s) => phaseAt(s.simTime, s.playing, mission ? landingEnd : Infinity))

  const nearby = useCallback((site: ChosenSite) => {
    const m = nearestMap(terrains, site)
    return m ? { label: m.t.label.split(',')[0].replace(/^LOLA /, ''), distanceKm: m.km } : null
  }, [terrains])

  // The 3D map uses grid azimuths (clockwise from the polar map's north); at longitude L, grid = compass + L.
  const simulate = useCallback(async (site: ChosenSite, time: string) => {
    const m = nearestMap(terrains, site)
    if (!m) return
    const { lat, lon } = m.t.sky as { lat: number; lon: number }
    const c = await fetchConditions({ lat, lon, start: time, days: 0.25, step_h: 0.25 })
    const grid = (az: number) => Math.round(((az + lon) % 360 + 360) % 360)
    if (m.t.id !== useSim.getState().terrainId) switchTerrain(m.t.id)
    const earthEl = Math.round(c.earth.elevation[0] * 10) / 10
    useSim.setState({
      mode: 'simulate', skyDate: time, sunAz: grid(c.sun.azimuth[0]), sunEl: Math.round(c.sun.elevation[0] * 10) / 10,
      earthAz: grid(c.earth.azimuth[0]), earthEl, missionEarthEl: earthEl,
    })
  }, [terrains])

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

  const steps = (
    <ol className="steps" aria-label="Mission phase">
      {STEPS.map(([id, label]) => {
        const now = mode === 'compare' ? id === 'compare' : id === phase
        return <li key={id} className={now ? 'now' : ''} aria-current={now ? 'step' : undefined}>{label}</li>
      })}
    </ol>
  )

  if (mode === 'compare') {
    return (
      <div className="app compare-app">
        <header className="top compare-top">
          <div className="brand"><h1>Echo-Path</h1>{steps}</div>
        </header>
        <CompareView nearby={nearby} onSimulate={(site, time) => void simulate(site, time)} />
      </div>
    )
  }

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
          {steps}
        </div>
        {mission && <Readout grid={mission.terrain} />}
        <div className="view-tools">
          <button type="button" className="quiet" onClick={() => set({ mode: 'compare', playing: false })}>‹ Compare sites and dates</button>
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
