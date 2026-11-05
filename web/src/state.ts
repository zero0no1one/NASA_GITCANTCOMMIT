import { create } from 'zustand'
import type { Mission, RoverPlan, TerrainInfo, Vec3 } from './api'

export type Layer = 'elevation' | 'hazard' | 'slope'

interface SimState {
  terrains: TerrainInfo[]
  terrainId: string
  earthEl: number | null      // null = this terrain's default sky (also the Sun and Earth azimuth below)
  earthAz: number | null
  outageStep: number | null   // null = first blocked comms sample
  mission: Mission | null
  missionError: string | null
  loading: boolean

  layer: Layer
  exaggeration: number
  follow: boolean

  touchdownRank: number       // 0 = nominal touchdown, 1..3 = ranked fallback
  goal: [number, number] | null
  roverSpeed: number
  maxSlope: number
  sunAz: number | null
  sunEl: number | null

  plan: RoverPlan | null
  planStart: number           // simulation time at which the current rover plan begins
  trail: Vec3[]               // ground already driven under earlier plans (engine x, y, z)
  roverError: string | null
  replanning: boolean

  simTime: number
  playing: boolean
  rate: number
  runId: number               // bumped to restart the run from descent (re-plans the rover from touchdown)

  set: (patch: Partial<SimState>) => void
}

export const useSim = create<SimState>((set) => ({
  terrains: [],
  terrainId: 'lola_site20',
  earthEl: null,
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
  trail: [],
  roverError: null,
  replanning: false,

  simTime: 0,
  playing: true,
  rate: 20,
  runId: 0,

  set: (patch) => set(patch),
}))

/** Start the run again from the top of the descent. */
export const restartRun = () =>
  useSim.setState((s) => ({ simTime: 0, plan: null, trail: [], playing: true, runId: s.runId + 1 }))
