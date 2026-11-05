import type { ReactNode } from 'react'
import type { Mission } from '../api'
import { restartRun, useSimInputs, type Layer } from '../state'

export function Controls({ mission }: { mission: Mission | null }) {
  const s = useSimInputs()
  const { set } = s
  const grid = mission?.terrain
  const width = grid ? (grid.cols - 1) * grid.dx : 1000
  const height = grid ? (grid.rows - 1) * grid.dy : 1000
  const sky = grid?.sky
  const earthEl = s.earthEl ?? mission?.earth.elevation_deg ?? 0
  const sunEl = s.sunEl ?? sky?.sun_el ?? 0

  return (
    <aside className="controls">
      <Section title="Terrain">
        <select value={s.terrainId} onChange={(e) => set({ terrainId: e.target.value, earthAz: null, earthEl: null, missionEarthEl: null, sunAz: null, sunEl: null, outageStep: null })}>
          {s.terrains.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
        </select>
        <div className="seg">
          {(['hazard', 'slope', 'elevation'] as Layer[]).map((l) => (
            <button key={l} className={s.layer === l ? 'on' : ''} onClick={() => set({ layer: l })}>{l}</button>
          ))}
        </div>
        <Slider label="Vertical exaggeration" value={s.exaggeration} min={1} max={6} step={0.5} unit="×"
          onChange={(v) => set({ exaggeration: v })} />
      </Section>

      <Section title="Lander outage">
        {mission && (
          <>
            <label className="field">
              <span>Comms lost at</span>
              <select value={s.outageStep ?? mission.outage.step}
                onChange={(e) => set({ outageStep: Number(e.target.value) })}>
                {mission.comms.slice(0, -1).map((c) => (
                  <option key={c.step} value={c.step}>
                    {c.time_s.toFixed(0)} s · {c.state === 0 ? 'blocked' : c.state === 1 ? 'clear' : 'unknown'}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Touchdown</span>
              <select value={s.touchdownRank} onChange={(e) => {
                set({ touchdownRank: Number(e.target.value) })
                restartRun()
              }}>
                <option value={0}>Nominal target (no divert)</option>
                {mission.fallbacks.map((f) => (
                  <option key={f.rank} value={f.rank}>Fallback #{f.rank} · H {f.hazard.toFixed(2)} · {f.slope_deg.toFixed(1)}°</option>
                ))}
              </select>
            </label>
            {mission.fallbacks.length === 0 && <p className="note bad">No feasible fallback from this outage.</p>}
          </>
        )}
        <Slider label="Earth elevation" value={earthEl} min={sky?.earth_el_min ?? -5} max={sky?.earth_el_max ?? 30} step={0.1} unit="°"
          onChange={(v) => set({ earthEl: v })} />
        {earthEl <= 0 && <p className="note warn">Earth is below the horizon, so there is no direct link.</p>}
        {sky && (
          <p className="note">
            {sky.horizon_km > 0
              ? `Range this site can see as the Moon librates. Terrain out to ${sky.horizon_km} km and lunar curvature are included.`
              : 'Test terrain: only this map can block the Earth or Sun.'}
          </p>
        )}
      </Section>

      <Section title="Rover">
        <Slider label="Goal X" value={s.goal?.[0] ?? 0} min={0} max={width} step={5} unit=" m"
          onChange={(v) => set({ goal: [v, s.goal?.[1] ?? height / 2] })} />
        <Slider label="Goal Y" value={s.goal?.[1] ?? 0} min={0} max={height} step={5} unit=" m"
          onChange={(v) => set({ goal: [s.goal?.[0] ?? width / 2, v] })} />
        <p className="note">Click the terrain to set a new goal. Changing anything here re-routes the rover from where it is now.</p>
        <Slider label="Drive speed" value={s.roverSpeed} min={0.05} max={2} step={0.05} unit=" m/s"
          onChange={(v) => set({ roverSpeed: v })} />
        <Slider label="Max slope" value={s.maxSlope} min={5} max={30} step={1} unit="°"
          onChange={(v) => set({ maxSlope: v })} />
        <Slider label="Sun azimuth" value={s.sunAz ?? sky?.sun_az ?? 90} min={0} max={359} step={1} unit="°"
          onChange={(v) => set({ sunAz: v })} />
        <Slider label="Sun elevation" value={sunEl} min={sky?.sun_el_min ?? -5} max={sky?.sun_el_max ?? 30} step={0.1} unit="°"
          onChange={(v) => set({ sunEl: v })} />
        {sunEl <= 0 && <p className="note warn">The Sun is below the horizon, so the rover runs on battery alone.</p>}
        <label className="check">
          <input type="checkbox" checked={s.follow} onChange={(e) => set({ follow: e.target.checked })} />
          Camera follows rover
        </label>
      </Section>
    </aside>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2>{title}</h2>
      {children}
    </section>
  )
}

function Slider({ label, value, min, max, step, unit, onChange }: {
  label: string; value: number; min: number; max: number; step: number; unit: string; onChange: (v: number) => void
}) {
  return (
    <label className="field">
      <span>{label}<b>{Number.isInteger(step) ? value.toFixed(0) : value.toFixed(step < 0.1 ? 2 : 1)}{unit}</b></span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  )
}
