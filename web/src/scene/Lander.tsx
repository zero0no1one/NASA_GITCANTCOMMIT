import { useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { Line } from '@react-three/drei'
import * as THREE from 'three'
import type { Mission, Vec3 } from '../api'
import { sampleField } from '../coords'
import { useSim } from '../state'
import { sampleFlight, type LanderTrack } from '../track'
import { toScene } from './geo'
import { TextLabel } from './Label'

const SCALE = 7          // drawn larger than life so a ~4 m lander is visible on a kilometre-wide map
const MAX_THRUST = 5000  // only sets how bright the plume looks

const noMotion = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

function LanderModel({ plume }: { plume: React.RefObject<THREE.Group | null> }) {
  const legs = [0, 1, 2, 3].map((i) => (i * Math.PI) / 2 + Math.PI / 4)
  return (
    <group scale={SCALE}>
      {/* Descent stage in gold foil, ascent-style cabin above it. */}
      <mesh position={[0, 1.15, 0]} castShadow>
        <cylinderGeometry args={[1, 1.1, 0.8, 8]} />
        <meshStandardMaterial color="#c8962b" metalness={0.85} roughness={0.32} />
      </mesh>
      <mesh position={[0, 1.95, 0]} castShadow>
        <boxGeometry args={[1.05, 0.8, 1.05]} />
        <meshStandardMaterial color="#d7d5ce" metalness={0.5} roughness={0.5} />
      </mesh>
      <mesh position={[0.32, 2.5, 0.2]} rotation={[0.5, 0.4, 0]}>
        <cylinderGeometry args={[0.26, 0.04, 0.16, 16, 1, true]} />
        <meshStandardMaterial color="#efebe1" side={THREE.DoubleSide} />
      </mesh>
      <mesh position={[0, 0.58, 0]}>
        <cylinderGeometry args={[0.2, 0.42, 0.4, 16, 1, true]} />
        <meshStandardMaterial color="#3d3a36" side={THREE.DoubleSide} metalness={0.7} roughness={0.4} />
      </mesh>
      {legs.map((a) => (
        <group key={a} rotation={[0, a, 0]}>
          <mesh position={[1.1, 0.5, 0]} rotation={[0, 0, 0.72]}>
            <cylinderGeometry args={[0.045, 0.045, 1.5, 6]} />
            <meshStandardMaterial color="#b9b5ab" metalness={0.6} roughness={0.4} />
          </mesh>
          <mesh position={[1.62, 0.04, 0]}>
            <cylinderGeometry args={[0.22, 0.26, 0.06, 12]} />
            <meshStandardMaterial color="#c8962b" metalness={0.7} roughness={0.4} />
          </mesh>
        </group>
      ))}
      <group ref={plume} position={[0, 0.34, 0]}>
        <mesh position={[0, -0.9, 0]} rotation={[Math.PI, 0, 0]}>
          <coneGeometry args={[0.36, 1.9, 16, 1, true]} />
          <meshBasicMaterial color="#9fc6ff" transparent opacity={0.55} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} />
        </mesh>
        <mesh position={[0, -0.45, 0]} rotation={[Math.PI, 0, 0]}>
          <coneGeometry args={[0.2, 0.9, 16, 1, true]} />
          <meshBasicMaterial color="#fff6d8" transparent opacity={0.85} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} />
        </mesh>
      </group>
    </group>
  )
}

interface Props {
  mission: Mission
  track: LanderTrack
  exaggeration: number
}

/** The route, where Earth is lost along it, and the lander flying it. */
export function Lander({ mission, track, exaggeration }: Props) {
  const grid = mission.terrain
  const camera = useThree((s) => s.camera)
  const controls = useThree((s) => s.controls) as unknown as { target: THREE.Vector3; update: () => void } | null
  const body = useRef<THREE.Group>(null)
  const plume = useRef<THREE.Group>(null)
  const stick = useRef<THREE.BufferGeometry>(null)
  const up = useMemo(() => new THREE.Vector3(), [])
  const want = useMemo(() => new THREE.Quaternion(), [])
  const yAxis = useMemo(() => new THREE.Vector3(0, 1, 0), [])

  // The route splits into runs by Earth link: solid gold while in contact, dashed orange when not.
  const route = useMemo(() => {
    const scene = (p: Vec3) => new THREE.Vector3(...toScene(grid, exaggeration, p[0], p[1], p[2]))
    const runs: { clear: boolean; points: THREE.Vector3[] }[] = []
    track.p.forEach((p, i) => {
      const clear = track.link[i] === 1
      const point = scene(p)
      const run = runs[runs.length - 1]
      if (run && run.clear === clear) run.points.push(point)
      else runs.push({ clear, points: run ? [run.points[run.points.length - 1], point] : [point] })
    })
    return { runs, marker: runs.find((r) => !r.clear)?.points[0] ?? null }
  }, [track, grid, exaggeration])

  useFrame((_, delta) => {
    const g = body.current
    if (!g) return
    const { simTime, view } = useSim.getState()
    const s = sampleFlight(track, simTime)
    const [x, y, z] = toScene(grid, exaggeration, s.position[0], s.position[1], s.position[2])
    const before = g.position.clone()
    g.position.set(x, y, z)
    const landed = simTime >= track.landing

    // Point the engine along the thrust it needs: the vehicle visibly leans into a divert.
    if (!landed) {
      up.set(s.accel[0], s.accel[2], -s.accel[1]).normalize()
      want.setFromUnitVectors(yAxis, up)
      g.quaternion.slerp(want, noMotion ? 1 : 1 - Math.exp(-delta * 4))
    } else {
      g.quaternion.identity()
    }

    if (plume.current) {
      plume.current.visible = !landed && simTime > 0
      const power = Math.min(s.thrust / MAX_THRUST, 1)
      const flicker = noMotion ? 1 : 0.92 + Math.random() * 0.16
      const length = (0.6 + power * 1.8) * flicker
      plume.current.scale.set(0.8 + power * 0.6, length, 0.8 + power * 0.6)
    }

    if (stick.current) {
      const ground = sampleField(grid, 'z', s.position[0], s.position[1]) ?? grid.z_min
      const [, gy] = toScene(grid, exaggeration, s.position[0], s.position[1], ground)
      stick.current.setFromPoints([new THREE.Vector3(x, y, z), new THREE.Vector3(x, gy + 1, z)])
    }

    if (view === 'follow' && controls && !landed) {
      const shift = g.position.clone().sub(before)
      if (shift.length() < 200) camera.position.add(shift)
      controls.target.lerp(g.position, 0.2)
      controls.update()
    }
  })

  return (
    <group>
      {route.runs.map((run, i) => run.points.length > 1 && (
        <Line key={i} points={run.points} color={run.clear ? '#e3b341' : '#ff7a45'} lineWidth={2.25} dashed={!run.clear} dashSize={10} gapSize={7} />
      ))}
      {route.marker && <TextLabel text="Earth lost" position={route.marker} color="#ff7a45" sizePx={13} opacity={1} />}
      <lineSegments>
        <bufferGeometry ref={stick} />
        <lineBasicMaterial color="#efebe1" transparent opacity={0.35} />
      </lineSegments>
      <group ref={body}>
        <LanderModel plume={plume} />
      </group>
    </group>
  )
}
