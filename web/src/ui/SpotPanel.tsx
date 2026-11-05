import { useEffect, useState, type FormEvent } from 'react'
import { fetchPoint, type Mission, type PointReport } from '../api'
import { formatPlace, groundVerdict, latLon, sampleField, toLocal } from '../coords'
import { useSimInputs, type Phase } from '../state'

/** The chosen spot, and the one action that makes sense for it in this phase. */
export function SpotPanel({ mission, phase, onAct }: { mission: Mission; phase: Phase; onAct: (x: number, y: number) => void }) {
  const { pin: chosenSpot, target, divertTo, goal, earthEl, sunAz, sunEl, terrainId, set } = useSimInputs()
  const grid = mission.terrain
  // A spot on a map that's still loading can't be read against the grid of the previous one.
  const pin = grid.id === terrainId ? chosenSpot : null
  const [report, setReport] = useState<PointReport | null>(null)
  const [lat, setLat] = useState('')
  const [lon, setLon] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const hasCoords = grid.origin_xy !== null

  useEffect(() => {
    if (!pin) return
    let live = true
    const timer = setTimeout(() => {
      fetchPoint({ terrain: grid.id, x: pin[0], y: pin[1], earth_el: earthEl, sun_az: sunAz, sun_el: sunEl })
        .then((r) => { if (live) setReport(r) })
        .catch(() => { if (live) setReport(null) })
    }, 150)
    return () => { live = false; clearTimeout(timer) }
  }, [pin, grid.id, earthEl, sunAz, sunEl])

  const goTo = (e: FormEvent) => {
    e.preventDefault()
    const a = Number(lat)
    const b = Number(lon)
    if (lat.trim() === '' || lon.trim() === '' || Number.isNaN(a) || Number.isNaN(b)) {
      setFormError(hasCoords ? 'Enter a latitude and longitude as numbers, such as -85.46 and 31.5.' : 'Enter east and north distances in metres.')
      return
    }
    const place = hasCoords ? toLocal(grid, a, b) : ([a, b] as [number, number])
    if (!place || sampleField(grid, 'z', place[0], place[1]) === null) {
      setFormError('Those coordinates are outside this map.')
      return
    }
    setFormError(null)
    set({ pin: place })
  }

  const here = pin ?? target
  const verdict = pin ? groundVerdict(grid, pin[0], pin[1]) : null
  const [north, east] = pin ? formatPlace(grid, pin[0], pin[1]) : ['', '']
  const samePlace = (a: [number, number] | null) => a !== null && pin !== null && Math.hypot(a[0] - pin[0], a[1] - pin[1]) < 1
  const isCurrent = phase === 'drive' ? samePlace(goal) : samePlace(divertTo ?? target)
  const action = phase === 'plan' ? 'Land here' : phase === 'descent' ? 'Divert here' : 'Drive here'
  const ll = here ? latLon(grid, here[0], here[1]) : null

  return (
    <section className="panel" aria-label="Selected spot">
      {pin && verdict ? (
        <>
          <h2>{north} {east}</h2>
          <p className={verdict.ok ? 'verdict go' : 'verdict warn'}>{verdict.text}</p>
          <dl className="stats compact">
            <div><dt>Slope</dt><dd>{(sampleField(grid, 'slope', pin[0], pin[1]) ?? 0).toFixed(1)}°</dd></div>
            <div><dt>Roughness</dt><dd>{(sampleField(grid, 'roughness', pin[0], pin[1]) ?? 0).toFixed(2)} m</dd></div>
            {report && Math.hypot(report.x_m - pin[0], report.y_m - pin[1]) < 1 && (
              <>
                <div><dt>Earth</dt><dd className={report.earth_visible ? 'earth' : 'warn'}>{report.earth_visible ? 'In view' : 'Hidden'}</dd></div>
                <div><dt>Sun</dt><dd className={report.sunlit ? '' : 'warn'}>{report.sunlit ? 'Sunlit' : 'In shadow'}</dd></div>
              </>
            )}
          </dl>
          {isCurrent ? (
            <p className="current-spot">{phase === 'drive' ? 'This is the rover’s goal.' : 'This is your target.'}</p>
          ) : (
            <button type="button" className={verdict.ok ? 'primary' : 'secondary'} onClick={() => onAct(pin[0], pin[1])}>{action}</button>
          )}
        </>
      ) : (
        <p className="note">Click anywhere on the Moon to check the ground there.</p>
      )}
      <form className="goto" onSubmit={goTo}>
        <p className="goto-title">Go to coordinates</p>
        <div className="goto-row">
          <label><span>{hasCoords ? 'Latitude' : 'East (m)'}</span>
            <input inputMode="decimal" value={lat} placeholder={ll ? ll[0].toFixed(3) : '100'} onChange={(e) => setLat(e.target.value)} />
          </label>
          <label><span>{hasCoords ? 'Longitude' : 'North (m)'}</span>
            <input inputMode="decimal" value={lon} placeholder={ll ? ll[1].toFixed(3) : '100'} onChange={(e) => setLon(e.target.value)} />
          </label>
          <button type="submit" className="secondary">Go</button>
        </div>
        {formError && <p className="note warn" role="alert">{formError}</p>}
      </form>
    </section>
  )
}

/** Things to adjust: the sky, the rover and how the map is drawn. */
export function SettingsPanel({ mission }: { mission: Mission }) {
  const s = useSimInputs()
  const { set } = s
  const sky = mission.terrain.sky
  const earthEl = s.earthEl ?? mission.earth.elevation_deg
  const sunEl = s.sunEl ?? sky.sun_el
  return (
    <details className="fold settings">
      <summary>Sky, rover and map settings</summary>
      <Slider label="Earth elevation" value={earthEl} min={sky.earth_el_min} max={sky.earth_el_max} step={0.1} unit="°" onChange={(v) => set({ earthEl: v })} />
      {earthEl <= 0 && <p className="note warn">Earth is below the horizon, so there is no direct link.</p>}
      <Slider label="Sun direction" value={s.sunAz ?? sky.sun_az} min={0} max={359} step={1} unit="°" onChange={(v) => set({ sunAz: v })} />
      <Slider label="Sun elevation" value={sunEl} min={sky.sun_el_min} max={sky.sun_el_max} step={0.1} unit="°" onChange={(v) => set({ sunEl: v })} />
      {sunEl <= 0 && <p className="note warn">The Sun is below the horizon, so the rover runs on battery alone.</p>}
      <p className="note">
        {sky.horizon_km > 0
          ? `These ranges are what this site can really see. Terrain out to ${sky.horizon_km} km and the Moon’s curvature can block both.`
          : 'Test terrain: only this map can block the Earth or Sun.'}
      </p>
      <Slider label="Rover speed" value={s.roverSpeed} min={0.05} max={2} step={0.05} unit=" m/s" onChange={(v) => set({ roverSpeed: v })} />
      <Slider label="Rover slope limit" value={s.maxSlope} min={5} max={30} step={1} unit="°" onChange={(v) => set({ maxSlope: v })} />
      <Slider label="Exaggerate height" value={s.exaggeration} min={1} max={5} step={0.5} unit="×" onChange={(v) => set({ exaggeration: v })} />
      <label className="check">
        <input type="checkbox" checked={s.showGrid} onChange={(e) => set({ showGrid: e.target.checked })} />
        Show coordinate grid
      </label>
    </details>
  )
}

function Slider({ label, value, min, max, step, unit, onChange }: {
  label: string; value: number; min: number; max: number; step: number; unit: string; onChange: (v: number) => void
}) {
  const shown = Number.isInteger(step) ? value.toFixed(0) : value.toFixed(step < 0.1 ? 2 : 1)
  return (
    <label className="field">
      <span>{label}<b>{shown}{unit}</b></span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  )
}
