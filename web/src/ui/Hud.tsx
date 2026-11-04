import type { Mission } from '../api'
import { useSim } from '../state'
import { formatClock, landerTrack, sampleRover } from '../track'

const COMMS_LABEL: Record<number, [string, string]> = { 1: ['Clear', 'ok'], 0: ['Blocked', 'bad'], [-1]: ['Unknown', 'warn'] }

export function Hud({ mission, landingEnd }: { mission: Mission; landingEnd: number }) {
  const simTime = useSim((s) => s.simTime)
  const plan = useSim((s) => s.plan)
  const planStart = useSim((s) => s.planStart)
  const rank = useSim((s) => s.touchdownRank)
  const replanning = useSim((s) => s.replanning)

  if (simTime < landingEnd) {
    const outage = landerTrack(mission, rank).outageTime
    const afterOutage = simTime >= outage
    const site = rank === 0 ? 'nominal target' : `fallback #${rank}`
    return (
      <div className="hud">
        <div className="hud-phase">Lander descent</div>
        <Row label="Mission time" value={`T+${formatClock(simTime)}`} />
        <Row label="Comms" value={afterOutage ? 'Lost' : 'Nominal'} tone={afterOutage ? 'bad' : 'ok'} />
        <Row label="Guidance" value={afterOutage ? `Diverting to ${site}` : 'Nominal descent'} />
        <Row label="Outage at" value={`T+${formatClock(outage)}`} />
      </div>
    )
  }

  const tl = plan?.timeline
  if (!tl) {
    return (
      <div className="hud">
        <div className="hud-phase">Landed</div>
        <Row label="Mission time" value={`T+${formatClock(simTime)}`} />
        <Row label="Rover" value={replanning ? 'Planning route…' : 'Waiting for a goal'} />
      </div>
    )
  }
  const r = sampleRover(tl, simTime - planStart)
  const [comms, tone] = COMMS_LABEL[r.comms] ?? COMMS_LABEL[-1]
  return (
    <div className="hud">
      <div className="hud-phase">{r.done ? 'Rover at goal' : 'Rover traverse'}{replanning ? ' · re-routing…' : ''}</div>
      <Row label="Mission time" value={`T+${formatClock(simTime)}`} />
      <Row label="Drive time" value={formatClock(simTime - landingEnd)} />
      <Row label="Speed" value={`${r.speed.toFixed(2)} m/s`} />
      <Row label="Heading" value={`${r.heading.toFixed(0).padStart(3, '0')}° ${compass(r.heading)}`} />
      <Row label="Battery" value={`${r.battery.toFixed(1)} %`} tone={r.battery < 20 ? 'bad' : r.battery < 50 ? 'warn' : 'ok'} />
      <Row label="Earth comms" value={comms} tone={tone} />
      <Row label="Sunlight" value={r.sunlit ? 'Sunlit' : 'Shadow'} tone={r.sunlit ? 'ok' : 'warn'} />
    </div>
  )
}

function Row({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="hud-row">
      <span>{label}</span>
      <b className={tone}>{value}</b>
    </div>
  )
}

function compass(deg: number) {
  return ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][Math.round(deg / 45) % 8]
}
