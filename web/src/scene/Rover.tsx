import { useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { Line } from '@react-three/drei'
import * as THREE from 'three'
import type { RoverTimeline, TerrainGrid } from '../api'
import { sampleField } from '../coords'
import { roverAt, useSim } from '../state'
import { sampleRover } from '../track'
import { toScene } from './geo'

const SCALE = 7   // drawn larger than life so a ~2 m rover is visible on a kilometre-wide map
const LINK = { clear: new THREE.Color('#79b4ff'), blocked: new THREE.Color('#ff7a45'), unknown: new THREE.Color('#b9b5ab') }

function RoverModel() {
  const wheels = [-0.8, 0, 0.8].flatMap((z) => [-0.75, 0.75].map((x) => [x, 0.3, z] as const))
  return (
    <group scale={SCALE}>
      <mesh position={[0, 0.7, 0]} castShadow>
        <boxGeometry args={[1.3, 0.45, 2]} />
        <meshStandardMaterial color="#d7d5ce" metalness={0.3} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.96, 0.15]} castShadow>
        <boxGeometry args={[1.55, 0.05, 1.5]} />
        <meshStandardMaterial color="#17325e" metalness={0.75} roughness={0.25} />
      </mesh>
      <mesh position={[0, 1.4, -0.75]}>
        <cylinderGeometry args={[0.05, 0.05, 0.9]} />
        <meshStandardMaterial color="#9c9a93" />
      </mesh>
      <mesh position={[0, 1.9, -0.75]} rotation={[Math.PI / 3, 0, 0]}>
        <coneGeometry args={[0.3, 0.2, 16, 1, true]} />
        <meshStandardMaterial color="#efebe1" side={THREE.DoubleSide} />
      </mesh>
      {/* Front marker, so heading changes are easy to see from above. */}
      <mesh position={[0, 0.75, -1.12]} rotation={[-Math.PI / 2, 0, 0]}>
        <coneGeometry args={[0.2, 0.35, 12]} />
        <meshStandardMaterial color="#e3b341" emissive="#e3b341" emissiveIntensity={0.5} />
      </mesh>
      {wheels.map(([x, y, z]) => (
        <mesh key={`${x},${z}`} position={[x, y, z]} rotation={[0, 0, Math.PI / 2]} castShadow>
          <cylinderGeometry args={[0.3, 0.3, 0.22, 16]} />
          <meshStandardMaterial color="#2d2c2a" roughness={0.9} />
        </mesh>
      ))}
    </group>
  )
}

interface Props {
  grid: TerrainGrid
  timeline: RoverTimeline
  exaggeration: number
}

/** The planned drive, coloured by the Earth link along it. */
export function RoverRoute({ grid, timeline, exaggeration, opacity = 1 }: Props & { opacity?: number }) {
  const route = useMemo(() => {
    const points = timeline.x.map((x, i) => {
      const [sx, sy, sz] = toScene(grid, exaggeration, x, timeline.y[i], timeline.z[i])
      return new THREE.Vector3(sx, sy + 1.5, sz)
    })
    const colors = timeline.comms.map((c) => (c === 1 ? LINK.clear : c === 0 ? LINK.blocked : LINK.unknown))
    return { points, colors }
  }, [grid, timeline, exaggeration])
  if (route.points.length < 2) return null
  return <Line points={route.points} vertexColors={route.colors} lineWidth={3} transparent={opacity < 1} opacity={opacity} />
}

export function Rover({ grid, timeline, exaggeration }: Props) {
  const body = useRef<THREE.Group>(null)
  const target = useMemo(() => new THREE.Quaternion(), [])
  const matrix = useMemo(() => new THREE.Matrix4(), [])
  const controls = useThree((s) => s.controls) as unknown as { target: THREE.Vector3; update: () => void } | null
  const camera = useThree((s) => s.camera)
  const placed = useRef(false)
  const history = useSim((s) => s.history)

  const trailPoints = useMemo(() => {
    const point = (x: number, y: number, z: number) => {
      const [a, b, c] = toScene(grid, exaggeration, x, y, z)
      return new THREE.Vector3(a, b + 1.5, c)
    }
    return history.flatMap((leg) => {
      const driven = leg.timeline.t.flatMap((t, i) =>
        t < leg.end - leg.start ? [point(leg.timeline.x[i], leg.timeline.y[i], leg.timeline.z[i])] : [])
      const last = sampleRover(leg.timeline, leg.end - leg.start)
      return [...driven, point(last.x, last.y, last.z)]
    })
  }, [grid, history, exaggeration])

  const forward = useMemo(() => new THREE.Vector3(), [])
  const normal = useMemo(() => new THREE.Vector3(), [])
  const right = useMemo(() => new THREE.Vector3(), [])

  useFrame((_, delta) => {
    const g = body.current
    if (!g) return
    const state = useSim.getState()
    const s = roverAt(state, state.simTime)
    g.visible = s !== null
    if (!s) return
    const [x, y, z] = toScene(grid, exaggeration, s.x, s.y, s.z)
    const before = g.position.clone()
    g.position.set(x, y, z)

    // Sit on the ground: wheels follow the terrain's slope, nose follows the heading (clockwise from north, -Z).
    const reach = grid.dx * 2
    const height = (px: number, py: number) => (sampleField(grid, 'z', px, py) ?? s.z) * exaggeration
    normal.set(height(s.x - reach, s.y) - height(s.x + reach, s.y), 2 * reach, -(height(s.x, s.y - reach) - height(s.x, s.y + reach))).normalize()
    const h = (s.heading * Math.PI) / 180
    forward.set(Math.sin(h), 0, -Math.cos(h))
    right.crossVectors(forward, normal).normalize()
    forward.crossVectors(normal, right).normalize()
    matrix.makeBasis(right, normal, forward.clone().negate())
    target.setFromRotationMatrix(matrix)
    if (!placed.current) {
      g.quaternion.copy(target)
      placed.current = true
    } else {
      g.quaternion.slerp(target, 1 - Math.exp(-delta * 6))
    }
    if (state.view === 'follow' && controls) {
      const shift = g.position.clone().sub(before)
      if (shift.length() < 200) camera.position.add(shift)
      controls.target.lerp(g.position, 0.2)
      controls.update()
    }
  })

  return (
    <group>
      <RoverRoute grid={grid} timeline={timeline} exaggeration={exaggeration} />
      {trailPoints.length > 1 && <Line points={trailPoints} color="#e3b341" lineWidth={2} dashed dashSize={6} gapSize={4} />}
      <group ref={body}>
        <RoverModel />
      </group>
    </group>
  )
}
