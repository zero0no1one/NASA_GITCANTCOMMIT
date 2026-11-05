import { useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { Line } from '@react-three/drei'
import * as THREE from 'three'
import type { RoverTimeline, TerrainGrid } from '../api'
import { useSim } from '../state'
import { sampleRover } from '../track'
import { toScene } from './geo'

const SCALE = 14   // drawn larger than life so a ~2 m rover is visible on a kilometre-wide map
const COMMS = { clear: new THREE.Color('#38bdf8'), blocked: new THREE.Color('#f43f5e'), unknown: new THREE.Color('#a855f7') }

interface Props {
  grid: TerrainGrid
  timeline: RoverTimeline
  exaggeration: number
}

function RoverModel() {
  const wheels = [-0.8, 0, 0.8].flatMap((z) => [-0.75, 0.75].map((x) => [x, 0.3, z] as const))
  return (
    <group scale={SCALE}>
      <mesh position={[0, 0.7, 0]} castShadow>
        <boxGeometry args={[1.3, 0.45, 2]} />
        <meshStandardMaterial color="#e5e7eb" metalness={0.3} roughness={0.5} />
      </mesh>
      <mesh position={[0, 0.96, 0.15]}>
        <boxGeometry args={[1.5, 0.05, 1.5]} />
        <meshStandardMaterial color="#1e3a8a" metalness={0.6} roughness={0.3} />
      </mesh>
      <mesh position={[0, 1.4, -0.75]}>
        <cylinderGeometry args={[0.05, 0.05, 0.9]} />
        <meshStandardMaterial color="#9ca3af" />
      </mesh>
      <mesh position={[0, 1.9, -0.75]} rotation={[Math.PI / 3, 0, 0]}>
        <coneGeometry args={[0.3, 0.2, 16, 1, true]} />
        <meshStandardMaterial color="#f8fafc" side={THREE.DoubleSide} />
      </mesh>
      {/* Forward marker so heading changes are easy to see. */}
      <mesh position={[0, 0.75, -1.1]} rotation={[-Math.PI / 2, 0, 0]}>
        <coneGeometry args={[0.2, 0.35, 12]} />
        <meshStandardMaterial color="#f59e0b" emissive="#f59e0b" emissiveIntensity={0.6} />
      </mesh>
      {wheels.map(([x, y, z]) => (
        <mesh key={`${x},${z}`} position={[x, y, z]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.3, 0.3, 0.22, 16]} />
          <meshStandardMaterial color="#374151" />
        </mesh>
      ))}
    </group>
  )
}

export function Rover({ grid, timeline, exaggeration }: Props) {
  const body = useRef<THREE.Group>(null)
  const target = useMemo(() => new THREE.Quaternion(), [])
  const euler = useMemo(() => new THREE.Euler(0, 0, 0, 'YXZ'), [])
  const controls = useThree((s) => s.controls) as unknown as { target: THREE.Vector3; update: () => void } | null
  const camera = useThree((s) => s.camera)
  const placed = useRef(false)
  const trail = useSim((s) => s.trail)
  const trailPoints = useMemo(
    () => trail.map(([x, y, z]) => toScene(grid, exaggeration, x, y, z)).map(([a, b, c]) => new THREE.Vector3(a, b + 1.5, c)),
    [grid, trail, exaggeration],
  )

  const route = useMemo(() => {
    const points = timeline.x.map((x, i) => {
      const [sx, sy, sz] = toScene(grid, exaggeration, x, timeline.y[i], timeline.z[i])
      return new THREE.Vector3(sx, sy + 1.5, sz)
    })
    const colors = timeline.comms.map((c) => (c === 1 ? COMMS.clear : c === 0 ? COMMS.blocked : COMMS.unknown))
    return { points, colors }
  }, [grid, timeline, exaggeration])

  useFrame((_, delta) => {
    const g = body.current
    if (!g) return
    const { simTime, planStart, follow } = useSim.getState()
    g.visible = simTime >= planStart
    if (!g.visible) return
    const s = sampleRover(timeline, simTime - planStart)
    const [x, y, z] = toScene(grid, exaggeration, s.x, s.y, s.z)
    const before = g.position.clone()
    g.position.set(x, y, z)
    // Heading is clockwise from north (-Z); turn smoothly so re-routes read as a visible steer.
    euler.set((s.pitch * Math.PI) / 180 * Math.min(exaggeration, 3), (-s.heading * Math.PI) / 180, 0)
    target.setFromEuler(euler)
    if (!placed.current) {
      g.quaternion.copy(target)
      placed.current = true
    } else {
      g.quaternion.slerp(target, 1 - Math.exp(-delta * 6))
    }
    if (follow && controls) {
      const shift = g.position.clone().sub(before)
      if (shift.length() < 200) camera.position.add(shift)
      controls.target.lerp(g.position, 0.2)
      controls.update()
    }
  })

  return (
    <group>
      {route.points.length > 1 && <Line points={route.points} vertexColors={route.colors} lineWidth={3} />}
      {trailPoints.length > 1 && <Line points={trailPoints} color="#cbd5e1" lineWidth={2.5} dashed dashSize={6} gapSize={4} />}
      <group ref={body}>
        <RoverModel />
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.5, 0]}>
          <ringGeometry args={[SCALE * 1.6, SCALE * 2, 40]} />
          <meshBasicMaterial color="#f59e0b" transparent opacity={0.85} side={THREE.DoubleSide} />
        </mesh>
      </group>
    </group>
  )
}
