import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { fetchCatalog, fetchConditions, type Catalog, type Conditions } from '../../api'
import { formatLat, formatLon } from '../../coords'
import { CompareTable } from './CompareTable'
import { HorizonChart } from './HorizonChart'
import { Timelines } from './Timelines'
import { LUNAR_DAY_DAYS, clampStart, formatHours, formatUtc, hoursUntilChange, thisHour, toInput, toMs } from './time'

export interface ChosenSite {
  key: string
  name: string
  lat: number
  lon: number
}

/** A 3D landing terrain near the site in focus, if there is one. */
export interface Nearby {
  label: string
  distanceKm: number
}

const MAX_SITES = 4
const DEFAULT_SITES = ['site01', 'site20', 'site23', 'apollo-11']
const SPANS: [number, string][] = [[14, '14 days'], [LUNAR_DAY_DAYS, 'One lunar day (29.5 days)'], [60, '60 days']]
const keyOf = (lat: number, lon: number) => `${lat.toFixed(4)},${lon.toFixed(4)}`
const angle = (el: number) => (el >= 0 ? `${el.toFixed(1)}° above the horizon` : `${Math.abs(el).toFixed(1)}° below it`)

/** Choose sites and dates, then see the Sun and Earth against each site's skyline, side by side. */
export function CompareView({ nearby, onSimulate }: {
  nearby: (site: ChosenSite) => Nearby | null
  onSimulate: (site: ChosenSite, time: string) => void
}) {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sites, setSites] = useState<ChosenSite[]>([])
  const [focus, setFocus] = useState('')
  const [startMs, setStartMs] = useState(thisHour)
  const [days, setDays] = useState(LUNAR_DAY_DAYS)
  const [results, setResults] = useState<Record<string, Conditions | Error>>({})
  const [cursor, setCursor] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [pick, setPick] = useState('')
  const [lat, setLat] = useState('')
  const [lon, setLon] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    fetchCatalog().then((c) => {
      setCatalog(c)
      const chosen = DEFAULT_SITES.map((id) => c.sites.find((s) => s.id === id)).filter((s) => s !== undefined)
        .map((s) => ({ key: keyOf(s.lat, s.lon), name: s.name, lat: s.lat, lon: s.lon }))
      setSites(chosen)
      setFocus(chosen[0]?.key ?? '')
      setStartMs((ms) => clampStart(ms, LUNAR_DAY_DAYS, c.dates.first, c.dates.last))
    }).catch((e: Error) => setError(e.message))
  }, [])

  const stepH = days > 31 ? 2 : 1
  const start = `${toInput(startMs)}:00Z`
  useEffect(() => {
    let live = true
    for (const s of sites) {
      fetchConditions({ lat: s.lat, lon: s.lon, start, days, step_h: stepH })
        .then((c) => { if (live) setResults((r) => ({ ...r, [`${s.key}|${start}|${days}`]: c })) })
        .catch((e: Error) => { if (live) setResults((r) => ({ ...r, [`${s.key}|${start}|${days}`]: e })) })
    }
    return () => { live = false }
  }, [sites, start, days, stepH])

  const resultFor = (key: string) => {
    const r = results[`${key}|${start}|${days}`]
    return r instanceof Error ? null : r ?? null
  }
  const failure = sites.map((s) => results[`${s.key}|${start}|${days}`]).find((r) => r instanceof Error) as Error | undefined
  const focusSite = sites.find((s) => s.key === focus) ?? sites[0]
  const focused = focusSite ? resultFor(focusSite.key) : null
  const anyResult = sites.map((s) => resultFor(s.key)).find((r) => r !== null) ?? null
  const times = anyResult?.times ?? []
  const n = times.length
  const at = Math.min(cursor, Math.max(n - 1, 0))

  useEffect(() => {
    if (!playing || n < 2) return
    const advance = Math.max(1, Math.round(n / 360))
    const timer = setInterval(() => setCursor((c) => (c + advance >= n ? 0 : c + advance)), 50)
    return () => clearInterval(timer)
  }, [playing, n])

  const groups = useMemo(() => {
    const out = new Map<string, Catalog['sites']>()
    for (const s of catalog?.sites ?? []) out.set(s.group, [...(out.get(s.group) ?? []), s])
    return [...out.entries()]
  }, [catalog])

  const add = (site: ChosenSite) => {
    if (sites.some((s) => s.key === site.key)) { setFocus(site.key); return }
    if (sites.length >= MAX_SITES) { setFormError(`Compare up to ${MAX_SITES} sites at once. Remove one first.`); return }
    setFormError(null)
    setSites([...sites, site])
    setFocus(site.key)
  }
  const addPicked = () => {
    const s = catalog?.sites.find((c) => c.id === pick)
    if (s) add({ key: keyOf(s.lat, s.lon), name: s.name, lat: s.lat, lon: s.lon })
  }
  const addCustom = (e: FormEvent) => {
    e.preventDefault()
    const a = Number(lat)
    const b = Number(lon)
    if (lat.trim() === '' || lon.trim() === '' || !Number.isFinite(a) || !Number.isFinite(b) || Math.abs(a) > 90 || Math.abs(b) > 180) {
      setFormError('Enter a latitude from -90 to 90 and a longitude from -180 to 180, such as -84.6 and 31.0.')
      return
    }
    add({ key: keyOf(a, b), name: `${formatLat(a)} ${formatLon(b)}`, lat: a, lon: b })
  }
  const remove = (key: string) => {
    const rest = sites.filter((s) => s.key !== key)
    setSites(rest)
    if (focus === key) setFocus(rest[0]?.key ?? '')
  }
  const moveStart = (ms: number) => {
    if (!catalog || !Number.isFinite(ms)) return
    setStartMs(clampStart(Math.round(ms / 3600_000) * 3600_000, days, catalog.dates.first, catalog.dates.last))
    setCursor(0)
  }
  const changeSpan = (d: number) => {
    setDays(d)
    if (catalog) setStartMs((ms) => clampStart(ms, d, catalog.dates.first, catalog.dates.last))
    setCursor(0)
  }

  const now = focused && n ? {
    sunEl: focused.sun.elevation[at], sunLit: focused.sun.visible[at] >= 0.5, sunChange: hoursUntilChange(focused.sun.visible, at, focused.step_h),
    earthEl: focused.earth.elevation[at], earthUp: focused.earth.visible[at] >= 0.5, earthChange: hoursUntilChange(focused.earth.visible, at, focused.step_h),
    power: focused.power_w[at],
  } : null
  const near = focusSite ? nearby(focusSite) : null

  return (
    <div className="compare">
      <aside className="compare-side">
        <section className="panel" aria-label="Sites to compare">
          <h2>Landing sites</h2>
          <ul className="chips">
            {sites.map((s) => (
              <li key={s.key} className={`chip${s.key === focus ? ' focus' : ''}`}>
                <button type="button" className="chip-name" aria-pressed={s.key === focus} onClick={() => setFocus(s.key)}>{s.name}</button>
                <button type="button" className="chip-x" aria-label={`Remove ${s.name}`} onClick={() => remove(s.key)}>×</button>
              </li>
            ))}
          </ul>
          <div className="add-row">
            <select aria-label="Add a known landing site" value={pick} onChange={(e) => setPick(e.target.value)}>
              <option value="">Add a known site…</option>
              {groups.map(([group, list]) => (
                <optgroup key={group} label={group}>
                  {list.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </optgroup>
              ))}
            </select>
            <button type="button" className="secondary" onClick={addPicked} disabled={!pick}>Add</button>
          </div>
          <form className="goto" onSubmit={addCustom}>
            <p className="goto-title">Or any coordinates</p>
            <div className="goto-row">
              <label><span>Latitude</span><input inputMode="decimal" value={lat} placeholder="-84.6" onChange={(e) => setLat(e.target.value)} /></label>
              <label><span>Longitude</span><input inputMode="decimal" value={lon} placeholder="31.0" onChange={(e) => setLon(e.target.value)} /></label>
              <button type="submit" className="secondary">Add</button>
            </div>
          </form>
          {formError && <p className="note warn" role="alert">{formError}</p>}
        </section>

        <section className="panel" aria-label="Dates">
          <h2>When</h2>
          <label className="field">
            <span>Start (UTC)</span>
            <input type="datetime-local" className="date-input" step={3600} value={toInput(startMs)}
              min={catalog ? catalog.dates.first.slice(0, 16) : undefined} max={catalog ? catalog.dates.last.slice(0, 16) : undefined}
              onChange={(e) => moveStart(toMs(e.target.value))} />
          </label>
          <div className="date-buttons">
            <button type="button" className="quiet" onClick={() => moveStart(startMs - LUNAR_DAY_DAYS * 86400_000)}>‹ Lunar day earlier</button>
            <button type="button" className="quiet" onClick={() => moveStart(thisHour())}>Now</button>
            <button type="button" className="quiet" onClick={() => moveStart(startMs + LUNAR_DAY_DAYS * 86400_000)}>Lunar day later ›</button>
          </div>
          <label className="field">
            <span>Span</span>
            <select value={days} onChange={(e) => changeSpan(Number(e.target.value))}>
              {SPANS.map(([d, label]) => <option key={d} value={d}>{label}</option>)}
            </select>
          </label>
          {catalog && <p className="note">Sun and Earth positions from NASA JPL Horizons, {catalog.dates.first.slice(0, 4)} to {Number(catalog.dates.last.slice(0, 4)) - 1}.</p>}
        </section>

        <details className="fold explain">
          <summary>Why small changes matter so much</summary>
          <p className="note">Near the south pole the Sun never climbs more than a few degrees. It circles the whole sky just above the horizon, so a ridge a few kilometres away can hide it for days, while a peak nearby stays lit for most of the year.</p>
          <p className="note">Earth sits low there too. The Moon’s slow wobble (libration) raises and lowers it by up to about 7° over each month, so the same spot can have a direct link to Earth for weeks and then lose it.</p>
          <p className="note">Away from the poles, a lunar day lasts about 29.5 Earth days: roughly two weeks of sunlight, then two weeks of night.</p>
        </details>
      </aside>

      <main className="compare-main">
        {error && <p className="note warn">Can’t load the site list: {error}</p>}
        {failure && <p className="note warn">{failure.message}</p>}
        {focusSite && (
          <header className="focus-head">
            <h2>{focusSite.name}</h2>
            <p className="focus-place">{formatLat(focusSite.lat)} {formatLon(focusSite.lon)}{n ? ` · ${formatUtc(times[at])}` : ''}</p>
          </header>
        )}
        {now && (
          <dl className="now-grid">
            <div><dt>Sun</dt><dd className={now.sunLit ? '' : 'warn'}>{now.sunLit ? 'Sunlit' : now.sunEl > 0 ? 'Hidden by terrain' : 'Below the horizon'} · {angle(now.sunEl)}</dd>
              <dd className="sub">{now.sunChange === null ? `No ${now.sunLit ? 'sunset' : 'sunrise'} in this span` : `${now.sunLit ? 'Sets' : 'Rises'} in ${formatHours(now.sunChange)}`}</dd></div>
            <div><dt>Earth</dt><dd className={now.earthUp ? 'earth' : 'warn'}>{now.earthUp ? 'In view' : now.earthEl > 0 ? 'Hidden by terrain' : 'Below the horizon'} · {angle(now.earthEl)}</dd>
              <dd className="sub">{now.earthChange === null ? `No ${now.earthUp ? 'Earthset' : 'Earthrise'} in this span` : `${now.earthUp ? 'Sets' : 'Rises'} in ${formatHours(now.earthChange)}`}</dd></div>
            <div><dt>Solar power</dt><dd>{Math.round(now.power)} W</dd><dd className="sub">1 m² panel facing the Sun</dd></div>
          </dl>
        )}
        {focused ? <HorizonChart c={focused} cursor={at} name={focusSite?.name ?? ''} /> : sites.length > 0 && <p className="note">Working out the skyline…</p>}

        {n > 0 && (
          <div className="time-row">
            <button type="button" className="secondary" onClick={() => setPlaying(!playing)}>{playing ? 'Pause' : 'Play'}</button>
            <input type="range" min={0} max={n - 1} value={at} aria-label="Time within the span" onChange={(e) => { setPlaying(false); setCursor(Number(e.target.value)) }} />
          </div>
        )}
        {sites.length > 0 && n > 0 && (
          <Timelines rows={sites.map((s) => ({ key: s.key, name: s.name, c: resultFor(s.key) }))} times={times} cursor={at} focus={focus}
            onSeek={(i) => { setPlaying(false); setCursor(i) }} onFocus={setFocus} />
        )}
        {sites.length > 0 && (
          <CompareTable rows={sites.map((s) => ({ key: s.key, name: s.name, summary: resultFor(s.key)?.summary ?? null }))} focus={focus} onFocus={setFocus} />
        )}

        {focusSite && (
          <section className="simulate-row">
            {near ? (
              <>
                <p className="note">A detailed 3D landing map ({near.label}) is {near.distanceKm < 1 ? 'here' : `${near.distanceKm.toFixed(0)} km away`}. Fly a landing there with this moment’s Sun and Earth.</p>
                <button type="button" className="primary" disabled={!n} onClick={() => onSimulate(focusSite, times[at])}>Simulate landing here</button>
              </>
            ) : (
              <p className="note">3D landing simulation is available for sites near Leibnitz Beta and the Shackleton area, where Echo-Path has 5 m terrain.</p>
            )}
          </section>
        )}
      </main>
    </div>
  )
}
