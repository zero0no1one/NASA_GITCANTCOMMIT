import type { Mission } from '../api'
import { bearing, compass, sampleField } from '../coords'
import { useSim } from '../state'
import { formatClock, sampleFlight, type LanderTrack } from '../track'

const DRY_MASS = 700

/** During descent: the numbers a pilot would watch, largest first. */
export function FlightPanel({ mission, track }: { mission: Mission; track: LanderTrack }) {
  const simTime = useSim((s) => s.simTime)
  const notice = useSim((s) => s.notice)
  const diverting = useSim((s) => s.diverting)
  const s = sampleFlight(track, simTime)
  const [x, y, z] = s.position
  const ground = sampleField(mission.terrain, 'z', x, y) ?? z
  const end = track.p[track.p.length - 1]
  const range = Math.hypot(end[0] - x, end[1] - y)
  const course = bearing(end[0] - x, end[1] - y)
  const rate = -s.velocity[2]
  const lost = s.link !== 1
  return (
    <section className="panel" aria-label="Descent">
      <h2>Descending</h2>
      <p className="big-number">{Math.max(z - ground, 0).toFixed(0)} <small>m above the ground</small></p>
      <dl className="stats">
        <div><dt>Descent rate</dt><dd>{rate.toFixed(1)} m/s</dd></div>
        <div><dt>Ground speed</dt><dd>{Math.hypot(s.velocity[0], s.velocity[1]).toFixed(1)} m/s</dd></div>
        <div><dt>Distance to target</dt><dd>{range.toFixed(0)} m</dd></div>
        <div><dt>Bearing to target</dt><dd>{range < 1 ? 'Overhead' : `${course.toFixed(0)}° ${compass(course)}`}</dd></div>
        <div><dt>Fuel left</dt><dd>{Math.max(s.mass - DRY_MASS, 0).toFixed(0)} kg</dd></div>
        <div><dt>Touchdown in</dt><dd>{formatClock(track.landing - simTime)}</dd></div>
        <div><dt>Earth link</dt><dd className={lost ? 'warn' : 'earth'}>{lost ? 'Lost' : 'In contact'}</dd></div>
      </dl>
      {lost && <p className="note warn">No contact with Earth. The lander is flying the plan it carries.</p>}
      <p className="note">{diverting ? 'Working out a new route…' : 'Click the Moon, then Divert here, to send the lander somewhere else.'}</p>
      {notice && <p className="note warn" role="status">{notice}</p>}
    </section>
  )
}
