import { useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import { fetchHorizon, type HorizonGrid, type LandingSite, type Mission, type TerrainGrid } from '../api'
import { sampleField } from '../coords'
import { useSim, useSimInputs } from '../state'
import type { LanderTrack } from '../track'
import { direction, fromScene, toScene } from './geo'
import { Horizon, Terrain } from './Terrain'
import { Graticule, GroundMark, HoverReticle, SiteFlags } from './Overlays'
import { Sky } from './Sky'
import { Lander } from './Lander'
import { Rover } from './Rover'

const noMotion = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** Advances simulation time while playing; stops at the end of the lander + rover timeline. */
function Clock({ end, landingEnd }: { end: number; landingEnd: number }) {
  useFrame((_, delta) => {
    const { playing, rate, simTime, replanning, diverting, set } = useSim.getState()
    if (!playing || diverting || simTime >= end) return
    // The rover waits for its new route, so it doesn't jump ahead along it when the answer arrives.
    if (replanning && simTime >= landingEnd) return
    set({ simTime: Math.min(end, simTime + Math.min(delta, 0.1) * rate) })
  })
  return null
}

/** Finds the spot on the terrain under the cursor by walking the view ray across the elevation grid. */
function pickGround(grid: TerrainGrid, exaggeration: number, ray: THREE.Ray): [number, number] | null {
  const width = (grid.cols - 1) * grid.dx
  const height = (grid.rows - 1) * grid.dy
  const top = (grid.z_max - grid.z_min) * exaggeration
  const box = new THREE.Box3(new THREE.Vector3(-width / 2, -1, -height / 2), new THREE.Vector3(width / 2, top + 1, height / 2))
  const enter = ray.intersectBox(box, new THREE.Vector3())
  if (!enter) return null
  const groundAt = (p: THREE.Vector3) => {
    const [x, y] = fromScene(grid, p.x, p.z)
    const z = sampleField(grid, 'z', x, y)
    return z === null ? null : (z - grid.z_min) * exaggeration
  }
  const start = enter.distanceTo(ray.origin)
  const reach = Math.hypot(width, height, top)
  const steps = 160
  const point = new THREE.Vector3()
  let previous = start
  for (let i = 0; i <= steps; i++) {
    const t = start + (reach * i) / steps
    ray.at(t, point)
    const ground = groundAt(point)
    if (ground === null) {
      if (i > 0) return null
      continue
    }
    if (point.y <= ground) {
      let low = previous
      let high = t
      for (let k = 0; k < 8; k++) {
        const mid = (low + high) / 2
        ray.at(mid, point)
        const g = groundAt(point)
        if (g !== null && point.y <= g) high = mid
        else low = mid
      }
      ray.at(high, point)
      return fromScene(grid, point.x, point.z)
    }
    previous = t
  }
  return null
}

/** Pointer handling on the canvas: hover moves the reticle; a click (not a drag) chooses that spot. */
function Picker({ grid, exaggeration, onClick }: { grid: TerrainGrid; exaggeration: number; onClick: (x: number, y: number) => void }) {
  const gl = useThree((s) => s.gl)
  const camera = useThree((s) => s.camera)
  const raycaster = useMemo(() => new THREE.Raycaster(), [])
  const ndc = useMemo(() => new THREE.Vector2(), [])
  const callback = useRef(onClick)
  useEffect(() => { callback.current = onClick }, [onClick])

  useEffect(() => {
    const el = gl.domElement
    const locate = (e: PointerEvent) => {
      const r = el.getBoundingClientRect()
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
      raycaster.setFromCamera(ndc, camera)
      return pickGround(grid, exaggeration, raycaster.ray)
    }
    const press0 = { at: null as [number, number] | null }
    const frame = { id: 0 }
    const move = (e: PointerEvent) => {
      if (e.pointerType !== 'mouse' || frame.id) return
      frame.id = requestAnimationFrame(() => {
        frame.id = 0
        useSim.setState({ hover: e.buttons ? null : locate(e) })
      })
    }
    const press = (e: PointerEvent) => { press0.at = [e.clientX, e.clientY] }
    const release = (e: PointerEvent) => {
      if (press0.at && Math.hypot(e.clientX - press0.at[0], e.clientY - press0.at[1]) < 5) {
        const spot = locate(e)
        if (spot) callback.current(spot[0], spot[1])
      }
      press0.at = null
    }
    const leave = () => useSim.setState({ hover: null })
    el.addEventListener('pointermove', move)
    el.addEventListener('pointerdown', press)
    el.addEventListener('pointerup', release)
    el.addEventListener('pointerleave', leave)
    return () => {
      cancelAnimationFrame(frame.id)
      el.removeEventListener('pointermove', move)
      el.removeEventListener('pointerdown', press)
      el.removeEventListener('pointerup', release)
      el.removeEventListener('pointerleave', leave)
    }
  }, [gl, camera, raycaster, ndc, grid, exaggeration])
  return null
}

/** Moves the camera to a chosen view, then hands control back to the viewer. */
function CameraRig({ span, top }: { span: number; top: number }) {
  const camera = useThree((s) => s.camera)
  const controls = useThree((s) => s.controls) as unknown as { target: THREE.Vector3; update: () => void } | null
  const view = useSim((s) => s.view)
  const nonce = useSim((s) => s.viewNonce)
  const move = useRef<{ position: THREE.Vector3; target: THREE.Vector3 } | null>(null)

  useEffect(() => {
    const presets = {
      overview: { position: [span * 0.12, span * 0.85, span * 0.95], target: [0, top * 0.3, 0] },
      horizon: { position: [0, top + span * 0.03, span * 0.62], target: [0, top + span * 0.03, -span * 2] },
    } as const
    if (view === 'follow') return
    move.current = { position: new THREE.Vector3(...presets[view].position), target: new THREE.Vector3(...presets[view].target) }
  }, [view, nonce, span, top])

  useFrame((_, delta) => {
    if (!move.current || !controls) return
    const k = noMotion ? 1 : 1 - Math.exp(-delta * 2.8)
    camera.position.lerp(move.current.position, k)
    controls.target.lerp(move.current.target, k)
    controls.update()
    if (camera.position.distanceTo(move.current.position) < span * 0.002) move.current = null
  })
  return null
}

interface Props {
  mission: Mission
  track: LanderTrack
  end: number
  landingEnd: number
  phase: 'plan' | 'descent' | 'drive'
  onChooseSite: (site: LandingSite) => void
  onClickGround: (x: number, y: number) => void
}

export function Scene({ mission, track, end, landingEnd, phase, onChooseSite, onClickGround }: Props) {
  const { layer, exaggeration, plan, goal, sunAz, sunEl, earthEl, target, divertTo, pin, sites, showGrid, terrainId } = useSimInputs()
  const grid = mission.terrain
  // Just after switching maps, the sites and spots on hand belong to the map that's still loading.
  const mapReady = grid.id === terrainId
  const width = (grid.cols - 1) * grid.dx
  const height = (grid.rows - 1) * grid.dy
  const span = Math.max(width, height)
  const top = (grid.z_max - grid.z_min) * exaggeration
  const sunElevation = sunEl ?? grid.sky.sun_el
  const sun = useMemo(() => direction(sunAz ?? grid.sky.sun_az, sunElevation), [sunAz, sunElevation, grid.sky.sun_az])
  const earth = useMemo(() => direction(mission.earth.azimuth_deg, earthEl ?? mission.earth.elevation_deg), [mission.earth.azimuth_deg, earthEl, mission.earth.elevation_deg])
  const lit = sunElevation > 0
  const [horizons, setHorizons] = useState<Record<string, HorizonGrid>>({})
  const horizon = horizons[grid.id] ?? null

  useEffect(() => {
    let live = true
    fetchHorizon(grid.id)
      .then((h) => { if (live) setHorizons((old) => ({ ...old, [grid.id]: h })) })
      .catch(() => undefined) // the landscape is scenery; the app works without it
    return () => { live = false }
  }, [grid.id])

  const shadowSize = span * 0.8
  const fogNear = span * 5
  const fogFar = span * 12
  const centre = toScene(grid, exaggeration, width / 2, height / 2, grid.z_min)

  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.15 }}
      camera={{ position: [span * 0.12, span * 0.85, span * 0.95], fov: 42, near: 1, far: span * 80 }}
    >
      <color attach="background" args={['#000000']} />
      <fog attach="fog" args={['#000000', fogNear, fogFar]} />
      <Sky span={span} sun={sun} earth={earth} />
      {/* Almost no ambient light: lunar shadows are dark, with a faint fill from earthshine so they aren't dead black. */}
      <hemisphereLight args={['#7f9fd0', '#1c1b19', lit ? 0.26 : 0.42]} />
      <directionalLight
        position={[sun[0] * span * 1.2 + centre[0], Math.max(sun[1], 0.02) * span * 1.2, sun[2] * span * 1.2 + centre[2]]}
        intensity={lit ? 8 : 0}
        castShadow
        shadow-mapSize={[4096, 4096]}
        shadow-camera-left={-shadowSize}
        shadow-camera-right={shadowSize}
        shadow-camera-top={shadowSize}
        shadow-camera-bottom={-shadowSize}
        shadow-camera-near={1}
        shadow-camera-far={span * 3}
        shadow-bias={-0.0004}
        shadow-normalBias={1.5}
      />
      {horizon && horizon.rows > 0 && <Horizon grid={grid} horizon={horizon} exaggeration={exaggeration} />}
      <Terrain grid={grid} layer={layer} exaggeration={exaggeration} />
      {showGrid && <Graticule grid={grid} exaggeration={exaggeration} />}
      {mapReady && phase === 'plan' && <SiteFlags grid={grid} exaggeration={exaggeration} sites={sites} onPick={onChooseSite} />}
      {mapReady && (divertTo ?? target) && <GroundMark grid={grid} exaggeration={exaggeration} at={(divertTo ?? target)!} color="#e3b341" scale={1.3} />}
      {mapReady && pin && <GroundMark grid={grid} exaggeration={exaggeration} at={pin} color="#efebe1" />}
      {goal && phase === 'drive' && <GroundMark grid={grid} exaggeration={exaggeration} at={goal} color="#79b4ff" scale={1.3} />}
      <HoverReticle grid={grid} exaggeration={exaggeration} />
      <Lander mission={mission} track={track} exaggeration={exaggeration} />
      {plan?.timeline && phase === 'drive' && <Rover grid={grid} timeline={plan.timeline} exaggeration={exaggeration} />}
      <OrbitControls makeDefault target={[0, top * 0.3, 0]} maxPolarAngle={Math.PI / 2.02} maxDistance={span * 5} minDistance={span * 0.04} />
      <CameraRig span={span} top={top} />
      <Picker grid={grid} exaggeration={exaggeration} onClick={onClickGround} />
      <Clock end={end} landingEnd={landingEnd} />
    </Canvas>
  )
}
