import { useSim } from './state'
import { usePlanner } from './usePlanner'
import { Scene } from './scene/Scene'
import { Hud } from './ui/Hud'
import { Timeline } from './ui/Timeline'
import { Controls } from './ui/Controls'

export default function App() {
  const { landingEnd, end } = usePlanner()
  const mission = useSim((s) => s.mission)
  const loading = useSim((s) => s.loading)
  const missionError = useSim((s) => s.missionError)
  const roverError = useSim((s) => s.roverError)
  const terrains = useSim((s) => s.terrains)
  const label = terrains.find((t) => t.id === mission?.terrain.id)?.label ?? mission?.terrain.id

  return (
    <div className="app">
      <header>
        <h1>Echo-Path <span>lunar lander + rover simulation</span></h1>
        {mission && (
          <div className="stats">
            <span>{label}</span>
            <span>{mission.terrain.cols}×{mission.terrain.rows} @ {mission.terrain.dx} m</span>
            <span>eligible {mission.eligible_pct.toFixed(0)}%</span>
            <span>comms blocked {mission.comms.filter((c) => c.state === 0).length}/{mission.comms.length}</span>
            <span>{mission.terrain.sky.horizon_km > 0 ? `horizons to ${mission.terrain.sky.horizon_km} km` : 'horizons: this map only'}</span>
          </div>
        )}
      </header>
      <main>
        <div className="viewport">
          {mission ? <Scene mission={mission} end={end} /> : (
            <div className="placeholder">{missionError ? '' : 'Loading lunar terrain… on the free server this can take a minute after it has been idle.'}</div>
          )}
          {mission && <Hud mission={mission} landingEnd={landingEnd} />}
          <div className="banners">
            {loading && mission && <div className="banner">Updating mission…</div>}
            {missionError && (
              <div className="banner bad">
                Server: {missionError}. {import.meta.env.DEV ? 'Is the Python API running on port 8000?' : 'Please reload in a moment.'}
              </div>
            )}
            {mission && !mission.nominal.feasible && (
              <div className="banner bad">Nominal descent fails: {mission.nominal.reasons.join('; ')}</div>
            )}
            {roverError && <div className="banner warn">Rover: {roverError}</div>}
          </div>
        </div>
        <Controls mission={mission} />
      </main>
      {mission && <Timeline end={end} landingEnd={landingEnd} />}
    </div>
  )
}
