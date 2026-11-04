import { useEffect, useMemo, useRef } from 'react'
import { fetchMission, fetchRover, fetchTerrains } from './api'
import type { Vec3 } from './api'
import { restartRun, useSim } from './state'
import { landerTrack, locate, sampleRover } from './track'

/** Loads terrains and missions, and re-plans the rover whenever its inputs change. */
export function usePlanner() {
  const s = useSim()
  const { set } = s

  useEffect(() => {
    fetchTerrains().then((terrains) => set({ terrains })).catch((e: Error) => set({ missionError: e.message }))
  }, [set])

  // Lander mission: refetch when its inputs change, then restart the simulation from descent.
  useEffect(() => {
    let live = true
    const timer = setTimeout(() => {
      set({ loading: true })
      fetchMission({ terrain: s.terrainId, earth_el: s.earthEl, earth_az: s.earthAz, outage_step: s.outageStep })
        .then((mission) => {
          if (!live) return
          const t = mission.terrain
          const fresh = useSim.getState().mission?.terrain.id !== t.id
          set({
            mission, missionError: null, loading: false, simTime: 0, plan: null, trail: [],
            ...(fresh ? { goal: [0.85 * (t.cols - 1) * t.dx, 0.85 * (t.rows - 1) * t.dy] as [number, number] } : {}),
          })
        })
        .catch((e: Error) => live && set({ missionError: e.message, loading: false }))
    }, 250)
    return () => {
      live = false
      clearTimeout(timer)
    }
  }, [s.terrainId, s.earthEl, s.earthAz, s.outageStep, set])

  // Choosing another touchdown restarts the run so the rover hands off from the new site.
  const firstRank = useRef(true)
  useEffect(() => {
    if (firstRank.current) {
      firstRank.current = false
      return
    }
    restartRun()
  }, [s.touchdownRank])

  const landingEnd = useMemo(() => {
    if (!s.mission) return 0
    const track = landerTrack(s.mission, s.touchdownRank)
    return track.t[track.t.length - 1]
  }, [s.mission, s.touchdownRank])

  // Rover plan: from the touchdown before/at landing, otherwise from wherever the rover is right now.
  const request = useRef(0)
  const { mission, goal, touchdownRank, roverSpeed, maxSlope, sunAz, sunEl } = s
  useEffect(() => {
    if (!mission || !goal) return
    const timer = setTimeout(() => {
      const now = useSim.getState()
      const track = landerTrack(mission, now.touchdownRank)
      const touchdown = track.p[track.p.length - 1]
      let start: [number, number] = [touchdown[0], touchdown[1]]
      let battery = 100
      let planStart = landingEnd
      if (now.plan?.timeline && now.simTime > now.planStart && now.simTime > landingEnd) {
        const here = sampleRover(now.plan.timeline, now.simTime - now.planStart)
        start = [here.x, here.y]
        battery = here.battery
        planStart = now.simTime
      }
      const id = ++request.current
      set({ replanning: true })
      fetchRover({
        terrain: mission.terrain.id, start, goal, earth_az: mission.earth.azimuth_deg, earth_el: now.earthEl,
        sun_az: now.sunAz, sun_el: now.sunEl, max_slope: now.maxSlope, speed: now.roverSpeed,
        start_battery_pct: Math.max(0, Math.min(100, battery)),
      })
        .then((plan) => {
          if (id !== request.current) return
          if (!plan.timeline) {
            set({ roverError: plan.reason, replanning: false })
            return
          }
          // Keep the ground already covered under the old plan so the turn onto the new route stays visible.
          const old = useSim.getState()
          let trail = old.trail
          if (old.plan?.timeline && planStart > old.planStart) {
            const tl = old.plan.timeline
            const [last] = locate(tl.t, planStart - old.planStart)
            const driven: Vec3[] = tl.t.slice(0, last + 1).map((_, i) => [tl.x[i], tl.y[i], tl.z[i]])
            const here = sampleRover(tl, planStart - old.planStart)
            trail = [...trail, ...driven, [here.x, here.y, here.z]]
          }
          set({ plan, planStart, trail, roverError: plan.reason, replanning: false })
        })
        .catch((e: Error) => id === request.current && set({ roverError: e.message, replanning: false }))
    }, 300)
    return () => clearTimeout(timer)
    // touchdownRank, rover and Sun settings are read from the store at request time but must still trigger a re-plan.
  }, [mission, goal, touchdownRank, roverSpeed, maxSlope, sunAz, sunEl, landingEnd, s.runId, set])

  const end = Math.max(landingEnd, s.plan?.timeline ? s.planStart + s.plan.timeline.t[s.plan.timeline.t.length - 1] : 0)
  return { landingEnd, end }
}
