import { useMemo } from 'react'
import type { Conditions } from '../../api'

const W = 720
const H = 270
const PAD = { left: 40, right: 10, top: 12, bottom: 28 }
const COMPASS: [number, string][] = [[0, 'N'], [45, 'NE'], [90, 'E'], [135, 'SE'], [180, 'S'], [225, 'SW'], [270, 'W'], [315, 'NW'], [360, 'N']]

/** The view all around the site: terrain skyline, and where the Sun and Earth travel against it over the span. */
export function HorizonChart({ c, cursor, name }: { c: Conditions; cursor: number; name: string }) {
  const scale = useMemo(() => {
    const skylineMax = Math.max(...c.horizon)
    const skylineMin = Math.min(...c.horizon)
    const bodiesMax = Math.max(...c.sun.elevation, ...c.earth.elevation)
    const top = Math.min(90, Math.max(8, Math.ceil(Math.max(bodiesMax, skylineMax) + 2)))
    const bottom = Math.max(-20, Math.min(-3, Math.floor(skylineMin - 1.5)))
    const step = top - bottom > 40 ? 15 : top - bottom > 16 ? 5 : 2
    return { top, bottom, step }
  }, [c])
  const x = (az: number) => PAD.left + (az / 360) * (W - PAD.left - PAD.right)
  const y = (el: number) => PAD.top + ((scale.top - el) / (scale.top - scale.bottom)) * (H - PAD.top - PAD.bottom)
  const inRange = (el: number) => el >= scale.bottom && el <= scale.top
  const floor = H - PAD.bottom

  const outline = [...c.horizon, c.horizon[0]].map((el, az) => `${x(az).toFixed(1)},${y(Math.max(el, scale.bottom)).toFixed(1)}`)
  const skyline = `M${x(0)},${floor} L${outline.join(' L')} L${x(360)},${floor} Z`

  const dots = (track: Conditions['sun'], cls: string) => track.azimuth.map((az, i) => (
    inRange(track.elevation[i])
      ? <circle key={i} className={`${cls}${track.visible[i] >= 0.5 ? '' : ' hidden'}`} cx={x(az)} cy={y(track.elevation[i])} r={1.4} />
      : null
  ))

  const ticks: number[] = []
  for (let v = Math.ceil(scale.bottom / scale.step) * scale.step; v <= scale.top; v += scale.step) ticks.push(v)
  const sun = { az: c.sun.azimuth[cursor], el: c.sun.elevation[cursor], seen: c.sun.visible[cursor] >= 0.5 }
  const earth = { az: c.earth.azimuth[cursor], el: c.earth.elevation[cursor], seen: c.earth.visible[cursor] >= 0.5 }

  return (
    <figure className="horizon-figure">
      <svg className="horizon-chart" viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label={`${name}: the terrain skyline in every direction, with the paths of the Sun and Earth over the chosen span`}>
        {ticks.map((v) => (
          <g key={v}>
            <line className={v === 0 ? 'grid zero' : 'grid'} x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} />
            <text className="axis" x={PAD.left - 6} y={y(v) + 4} textAnchor="end">{v}°</text>
          </g>
        ))}
        <path className="skyline" d={skyline} />
        {dots(c.earth, 'earth-dot')}
        {dots(c.sun, 'sun-dot')}
        {inRange(earth.el) && <circle className={`earth-now${earth.seen ? '' : ' hidden'}`} cx={x(earth.az)} cy={y(earth.el)} r={7} />}
        {inRange(sun.el) && <circle className={`sun-now${sun.seen ? '' : ' hidden'}`} cx={x(sun.az)} cy={y(sun.el)} r={8} />}
        {COMPASS.map(([az, label]) => (
          <text key={az} className={label.length === 1 ? 'axis cardinal' : 'axis'} x={x(az)} y={H - 8} textAnchor="middle">{label}</text>
        ))}
      </svg>
      <figcaption className="horizon-key">
        <span className="key-skyline">Terrain skyline (NASA LOLA)</span>
        <span className="key-sun">Sun</span>
        <span className="key-earth">Earth</span>
        <span className="key-hidden">Faded: behind terrain</span>
      </figcaption>
    </figure>
  )
}
