// Times in this screen are UTC throughout, as 'YYYY-MM-DDTHH:MM' for inputs and ISO strings from the API.

export const LUNAR_DAY_DAYS = 29.530589
const HOUR_MS = 3600_000

export const toMs = (utc: string) => Date.parse(utc.endsWith('Z') ? utc : `${utc}Z`)

/** 'YYYY-MM-DDTHH:MM' for a datetime-local input, read as UTC. */
export const toInput = (ms: number) => new Date(ms).toISOString().slice(0, 16)

export const formatUtc = (utc: string) => `${utc.slice(0, 10)} ${utc.slice(11, 16)} UTC`

/** Hours as a short duration: "5 h", "3 d 4 h". */
export function formatHours(hours: number) {
  if (hours <= 0) return 'none'
  if (hours < 1) return 'under 1 h'
  if (hours < 48) return `${Math.round(hours)} h`
  const days = Math.floor(hours / 24)
  const rest = Math.round(hours - days * 24)
  return rest ? `${days} d ${rest} h` : `${days} d`
}

/** Hours until a flag series changes from its value at `index`, or null if it doesn't change within the series. */
export function hoursUntilChange(visible: number[], index: number, stepH: number) {
  const now = visible[index] >= 0.5
  for (let j = index + 1; j < visible.length; j++) {
    if ((visible[j] >= 0.5) !== now) return (j - index) * stepH
  }
  return null
}

/** Runs of consecutive samples at or above half visible, as [first, last] sample indexes. */
export function runs(visible: number[]): [number, number][] {
  const out: [number, number][] = []
  let start = -1
  visible.forEach((v, i) => {
    if (v >= 0.5 && start < 0) start = i
    if ((v < 0.5 || i === visible.length - 1) && start >= 0) {
      out.push([start, v >= 0.5 ? i : i - 1])
      start = -1
    }
  })
  return out
}

/** Clamp a start time so the whole span fits inside the dates the ephemeris covers. */
export function clampStart(startMs: number, days: number, first: string, last: string) {
  const latest = toMs(last) - days * 24 * HOUR_MS
  return Math.min(Math.max(startMs, toMs(first)), latest)
}

/** The current hour, as the default start. */
export const thisHour = () => Math.floor(Date.now() / HOUR_MS) * HOUR_MS
