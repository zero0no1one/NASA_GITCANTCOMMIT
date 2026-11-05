import { create } from 'zustand'
import { useShallow } from 'zustand/react/shallow'
import type { Mission, RoverPlan, RoverTimeline, TerrainInfo } from './api'
import { sampleRover } from './track'

export type Layer = 'elevation' | 'hazard' | 'slope'

/** A stretch already driven under an earlier plan, from simulation time `start` up to `end`. */
export interface DrivenLeg {
  timeline: RoverTimeline
  start: number
  end: number
}

interface SimState {
  terrains: TerrainInfo[]
  terrainId: string
  earthEl: number | null          // null = this terrain's default sky (also the Sun and Earth azimuth below)
  missionEarthEl: number | null   // the Earth elevation the lander's descent was computed with
  earthAz: number | null
  outageStep: number | null       // null = first blocked comms sample
  mission: Mission | null
  missionError: string | null
  loading: boolean

  layer: Layer
  exaggeration: number
  follow: boolean

  touchdownRank: number           // 0 = nominal touchdown, 1..3 = ranked fallback
  goal: [number, number] | null
  roverSpeed: number
  maxSlope: number
  sunAz: number | null
  sunEl: number | null

  plan: RoverPlan | null
  planStart: number               // simulation time at which the current rover plan begins
  history: DrivenLeg[]
  roverError: string | null
  replanning: boolean

  simTime: number
  playing: boolean
  rate: number
  runId: number                   // bumped to restart the run from descent (re-plans the rover from touchdown)

  set: (patch: Partial<SimState>) => void
}

export const useSim = create<SimState>((set) => ({
  terrains: [],
  terrainId: 'lola_site20',
  earthEl: null,
  missionEarthEl: null,
  earthAz: null,
  outageStep: null,
  mission: null,
  missionError: null,
  loading: false,

  layer: 'hazard',
  exaggeration: 2,
  follow: false,

  touchdownRank: 1,
  goal: null,
  roverSpeed: 0.5,
  maxSlope: 20,
  sunAz: null,
  sunEl: null,

  plan: null,
  planStart: 0,
  history: [],
  roverError: null,
  replanning: false,

  simTime: 0,
  playing: true,
  rate: 20,
  runId: 0,

  set: (patch) => set(patch),
}))

/** All state except the clock. simTime changes every frame, so only components that show it should subscribe to it. */
export function useSimInputs() {
  return useSim(useShallow(({ simTime: _clock, ...inputs }) => inputs))
}

/** Start the run again from the top of the descent. */
export const restartRun = () =>
  useSim.setState((s) => ({ simTime: 0, plan: null, history: [], playing: true, runId: s.runId + 1, missionEarthEl: s.earthEl }))

/** Where the rover is at a simulation time, including earlier plans; null before it has rolled out. */
export function roverAt(s: Pick<SimState, 'plan' | 'planStart' | 'history'>, time: number) {
  if (s.plan?.timeline && time >= s.planStart) return sampleRover(s.plan.timeline, time - s.planStart)
  const leg = s.history.find((l) => time >= l.start && time < l.end)
  return leg ? sampleRover(leg.timeline, time - leg.start) : null
}
