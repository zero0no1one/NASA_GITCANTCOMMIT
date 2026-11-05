import { useEffect, useMemo, useRef } from 'react'
import { fetchMission, fetchRover, fetchSites, fetchTerrains } from './api'
import { roverAt, useSim, useSimInputs } from './state'
import { landerTrack } from './track'

/** Loads terrain, landing sites and the flight plan, and re-plans the rover whenever its inputs change. */
export function usePlanner() {
  const s = useSimInputs()
  const {
    set, mission, goal, touchdownRank, roverSpeed, maxSlope, sunAz, sunEl, earthEl, runId, terrainId, earthAz,
    missionEarthEl, outageStep, target, divert, sitesFor,
  } = s

  useEffect(() => {
    fetchTerrains().then((terrains) => set({ terrains })).catch((e: Error) => set({ missionError: e.message }))
  }, [set])

  const track = useMemo(() => (mission ? landerTrack(mission, touchdownRank, divert) : null), [mission, touchdownRank, divert])
  const landingEnd = track ? track.landing : 0

  // Ranked landing sites. They follow the sky, but never move a target that has already been chosen.
  const siteRequest = useRef(0)
  useEffect(() => {
    const id = ++siteRequest.current
    const timer = setTimeout(() => {
      fetchSites({ terrain: terrainId, earth_el: earthEl, earth_az: earthAz, sun_az: sunAz, sun_el: sunEl })
        .then(({ sites }) => {
          if (id !== siteRequest.current) return
          const now = useSim.getState()
          const first = sites[0] ? ([sites[0].x_m, sites[0].y_m] as [number, number]) : null
          set({ sites, sitesFor: terrainId, ...(now.target ? {} : { target: first, pin: first }) })
        })
        .catch((e: Error) => id === siteRequest.current && set({ missionError: e.message, sitesFor: terrainId }))
    }, 300)
    return () => clearTimeout(timer)
  }, [terrainId, earthEl, earthAz, sunAz, sunEl, set])

  // Once the rover is driving, the descent is history: moving Earth only re-plans the rover (below).
  useEffect(() => {
    const now = useSim.getState()
    if (!now.plan?.timeline || now.simTime < landingEnd) set({ missionEarthEl: earthEl })
  }, [earthEl, landingEnd, set])

  // Flight plan. A new terrain, target or outage goes back to the plan; a new Earth position updates it in place.
  const scenario = useRef('')
  const missionRequest = useRef(0)
  useEffect(() => {
    if (sitesFor !== terrainId) return
    const id = ++missionRequest.current
    // Marked straight away, not after the debounce: a run started on the outgoing plan would be cancelled by the new one.
    set({ loading: true })
    const timer = setTimeout(() => {
      fetchMission({ terrain: terrainId, target_xy: target, earth_el: missionEarthEl, earth_az: earthAz, outage_step: outageStep })
        .then((next) => {
          if (id !== missionRequest.current) return
          const now = useSim.getState()
          const key = `${terrainId}|${earthAz}|${outageStep}|${target}`
          const restart = scenario.current !== key
          scenario.current = key
          set({
            mission: next, missionError: null, loading: false,
            // A later outage can leave fewer backups; never keep pointing at one that no longer exists.
            touchdownRank: Math.min(now.touchdownRank, next.fallbacks.length),
            ...(restart ? { simTime: 0, plan: null, history: [], divert: null, divertTo: null, playing: false } : {}),
            ...(now.mission?.terrain.id !== next.terrain.id ? { goal: next.terrain.sky.goal_xy } : {}),
          })
        })
        .catch((e: Error) => id === missionRequest.current && set({ missionError: e.message, loading: false }))
    }, 200)
    return () => clearTimeout(timer)
  }, [terrainId, sitesFor, target, missionEarthEl, earthAz, outageStep, set])

  // Rover plan: from the touchdown before/at landing, otherwise from wherever the rover is right now.
  const request = useRef(0)
  useEffect(() => {
    if (!mission || !goal || !track) return
    const timer = setTimeout(() => {
      const now = useSim.getState()
      const touchdown = track.p[track.p.length - 1]
      let start: [number, number] = [touchdown[0], touchdown[1]]
      let battery = 100
      let planStart = landingEnd
      const here = now.simTime > landingEnd ? roverAt(now, now.simTime) : null
      if (here) {
        start = [here.x, here.y]
        battery = here.battery
        planStart = now.simTime
      }
      const id = ++request.current
      set({ replanning: true })
      fetchRover({
        terrain: mission.terrain.id, start, goal, earth_az: mission.earth.azimuth_deg,
        earth_el: now.earthEl ?? mission.earth.elevation_deg,
        sun_az: now.sunAz ?? mission.terrain.sky.sun_az, sun_el: now.sunEl ?? mission.terrain.sky.sun_el,
        max_slope: now.maxSlope, speed: now.roverSpeed,
        start_battery_pct: Math.max(0, Math.min(100, battery)),
      })
        .then((plan) => {
          if (id !== request.current) return
          if (!plan.timeline) {
            set({ roverError: plan.reason, replanning: false })
            return
          }
          // Keep what was driven before this moment, so the turn stays visible and the run can be scrubbed back.
          const old = useSim.getState()
          const history = old.history.filter((l) => l.start < planStart).map((l) => ({ ...l, end: Math.min(l.end, planStart) }))
          if (old.plan?.timeline && planStart > old.planStart) {
            history.push({ timeline: old.plan.timeline, start: old.planStart, end: planStart })
          }
          set({ plan, planStart, history, roverError: plan.reason, replanning: false })
        })
        .catch((e: Error) => id === request.current && set({ roverError: e.message, replanning: false }))
    }, 300)
    return () => clearTimeout(timer)
    // Rover, Sun and Earth settings are read from the store at request time but must still trigger a re-plan.
  }, [mission, goal, track, touchdownRank, roverSpeed, maxSlope, sunAz, sunEl, earthEl, landingEnd, runId, set])

  const end = Math.max(landingEnd, s.plan?.timeline ? s.planStart + s.plan.timeline.t[s.plan.timeline.t.length - 1] : 0)
  return { landingEnd, end, track }
}
