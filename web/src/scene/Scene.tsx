import { Canvas, useFrame } from '@react-three/fiber'
import { Line, OrbitControls, Stars } from '@react-three/drei'
import type { Mission } from '../api'
import { useSim } from '../state'
import { direction, toScene } from './geo'
import { Terrain } from './Terrain'
import { LanderScene } from './LanderScene'
import { Rover } from './Rover'

/** Advances simulation time while playing; stops at the end of the lander + rover timeline. */
function Clock({ end }: { end: number }) {
  useFrame((_, delta) => {
    const { playing, rate, simTime, set } = useSim.getState()
    if (!playing || simTime >= end) return
    set({ simTime: Math.min(end, simTime + Math.min(delta, 0.1) * rate) })
  })
  return null
}

export function Scene({ mission, end }: { mission: Mission; end: number }) {
  const { layer, exaggeration, touchdownRank, plan, goal, sunAz, sunEl, set } = useSim()
  const grid = mission.terrain
  const width = (grid.cols - 1) * grid.dx
  const height = (grid.rows - 1) * grid.dy
  const span = Math.max(width, height)
  const sunElevation = sunEl ?? grid.sky.sun_el
  const sun = direction(sunAz ?? grid.sky.sun_az, Math.max(sunElevation, 1))
  const earth = direction(mission.earth.azimuth_deg, mission.earth.elevation_deg)
  const centre = toScene(grid, exaggeration, width / 2, height / 2, (grid.z_min + grid.z_max) / 2)
  const goalPos = goal && toScene(grid, exaggeration, goal[0], goal[1], grid.z_max)

  return (
    <Canvas camera={{ position: [span * 0.15, span * 0.75, span * 0.85], fov: 45, near: 1, far: span * 20 }} shadows>
      <color attach="background" args={['#05070d']} />
      <Stars radius={span * 4} depth={span} count={3000} factor={span / 60} fade />
      <ambientLight intensity={0.25} />
      <directionalLight position={[sun[0] * span, sun[1] * span, sun[2] * span]} intensity={sunElevation > 0 ? 2.2 : 0.3} />
      <hemisphereLight args={['#c7d2fe', '#111827', 0.25]} />
      <Terrain grid={grid} layer={layer} exaggeration={exaggeration} onPick={(x, y) => set({ goal: [x, y] })} />
      <LanderScene mission={mission} exaggeration={exaggeration} rank={touchdownRank} />
      {plan?.timeline && <Rover grid={grid} timeline={plan.timeline} exaggeration={exaggeration} />}
      {goalPos && (
        <group position={goalPos}>
          <mesh position={[0, -((grid.z_max - grid.z_min) * exaggeration) / 2, 0]}>
            <cylinderGeometry args={[1.5, 1.5, (grid.z_max - grid.z_min) * exaggeration + 60, 8]} />
            <meshBasicMaterial color="#f59e0b" transparent opacity={0.7} />
          </mesh>
        </group>
      )}
      {/* Earth direction from the map centre. */}
      <Line points={[centre, [centre[0] + earth[0] * span * 0.45, centre[1] + earth[1] * span * 0.45, centre[2] + earth[2] * span * 0.45]]}
        color="#60a5fa" lineWidth={2} dashed dashSize={20} gapSize={12} />
      <mesh position={[centre[0] + earth[0] * span * 0.47, centre[1] + earth[1] * span * 0.47, centre[2] + earth[2] * span * 0.47]}>
        <sphereGeometry args={[span * 0.015, 24, 24]} />
        <meshStandardMaterial color="#3b82f6" emissive="#1d4ed8" emissiveIntensity={0.8} />
      </mesh>
      <OrbitControls makeDefault target={[0, 0, 0]} maxPolarAngle={Math.PI / 2.05} />
      <Clock end={end} />
    </Canvas>
  )
}
