import { create } from 'zustand'
import { useShallow } from 'zustand/react/shallow'
import type { LandingSite, Mission, RoverPlan, RoverTimeline, TerrainInfo } from './api'
import { sampleRover, type Divert } from './track'

export type Layer = 'surface' | 'safety' | 'slope' | 'elevation'
export type CameraView = 'overview' | 'horizon' | 'follow'
export type Phase = 'plan' | 'descent' | 'drive'
export type Mode = 'compare' | 'simulate'

/** A stretch already driven under an earlier plan, from simulation time `start` up to `end`. */
export interface DrivenLeg {
  timeline: RoverTimeline
  start: number
  end: number
}

interface SimState {
  mode: Mode                      // comparing sites and dates, or simulating a landing in 3D
  skyDate: string | null          // the UTC time the 3D sky was set from, until a sky slider moves it
  terrains: TerrainInfo[]
  terrainId: string
  earthEl: number | null          // null = this terrain's default sky (also the Sun and Earth azimuth below)
  missionEarthEl: number | null   // the Earth elevation the lander's descent was computed with
  earthAz: number | null
  outageStep: number | null       // null = first blocked comms sample
  mission: Mission | null
  missionError: string | null
  loading: boolean

  sites: LandingSite[]
  sitesFor: string | null         // the terrain the current site list belongs to
  target: [number, number] | null // where the lander is told to land
  pin: [number, number] | null    // the spot being inspected
  hover: [number, number] | null  // the spot under the cursor
  divert: Divert | null
  divertTo: [number, number] | null // where an in-flight divert is heading; the planned target stays as it was
  diverting: boolean              // the clock holds while a new route is being worked out
  notice: string | null           // a short message about the last action, such as a divert that failed

  layer: Layer
  exaggeration: number
  showGrid: boolean
  view: CameraView
  viewNonce: number               // bumped to re-run a camera move

  touchdownRank: number           // 0 = stay on target, 1..3 = switch to this backup when Earth is lost
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
  mode: 'compare',
  skyDate: null,
  terrains: [],
  terrainId: 'lola_site20',
  earthEl: null,
  missionEarthEl: null,
  earthAz: null,
  outageStep: null,
  mission: null,
  missionError: null,
  loading: false,

  sites: [],
  sitesFor: null,
  target: null,
  pin: null,
  hover: null,
  divert: null,
  divertTo: null,
  diverting: false,
  notice: null,

  layer: 'surface',
  exaggeration: 1.5,
  showGrid: true,
  view: 'overview',
  viewNonce: 0,

  touchdownRank: 0,
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
  playing: false,
  rate: 10,
  runId: 0,

  set: (patch) => set(patch),
}))

/** All state except the values that change constantly, so only components that show those re-render with them. */
export function useSimInputs() {
  return useSim(useShallow(({ simTime: _clock, hover: _hover, ...inputs }) => inputs))
}

/** Back to the plan: the run waits at the top of the descent until it is started again. */
export const restartRun = () =>
  useSim.setState((s) => ({ simTime: 0, plan: null, history: [], divert: null, divertTo: null, notice: null, playing: false, runId: s.runId + 1, missionEarthEl: s.earthEl }))

/** Where the rover is at a simulation time, including earlier plans; null before it has rolled out. */
export function roverAt(s: Pick<SimState, 'plan' | 'planStart' | 'history'>, time: number) {
  if (s.plan?.timeline && time >= s.planStart) return sampleRover(s.plan.timeline, time - s.planStart)
  const leg = s.history.find((l) => time >= l.start && time < l.end)
  return leg ? sampleRover(leg.timeline, time - leg.start) : null
}

/** Which part of the run a simulation time falls in. */
export function phaseAt(simTime: number, playing: boolean, landing: number): Phase {
  if (simTime >= landing) return 'drive'
  return simTime > 0 || playing ? 'descent' : 'plan'
}
