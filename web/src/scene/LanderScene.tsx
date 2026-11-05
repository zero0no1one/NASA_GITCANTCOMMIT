import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Line } from '@react-three/drei'
import * as THREE from 'three'
import type { Mission } from '../api'
import { useSim } from '../state'
import { landerTrack, samplePath } from '../track'
import { toScene } from './geo'

const FALLBACK_COLORS = ['#facc15', '#34d399', '#c084fc']
const COMMS_COLORS: Record<number, string> = { 0: '#f43f5e', 1: '#38bdf8', [-1]: '#a855f7' }

interface Props {
  mission: Mission
  exaggeration: number
  rank: number
}

/** Nominal descent, comms samples, ranked fallbacks and an animated lander marker. */
export function LanderScene({ mission, exaggeration, rank }: Props) {
  const grid = mission.terrain
  const place = (p: number[]) => toScene(grid, exaggeration, p[0], p[1], p[2])
  const track = useMemo(() => landerTrack(mission, rank), [mission, rank])
  const lander = useRef<THREE.Group>(null)
  const lines = useMemo(() => {
    const scene = (p: number[]) => toScene(grid, exaggeration, p[0], p[1], p[2])
    return { nominal: mission.nominal.path.map(scene), fallbacks: mission.fallbacks.map((f) => f.path.map(scene)) }
  }, [grid, mission, exaggeration])

  useFrame(() => {
    const { simTime } = useSim.getState()
    const g = lander.current
    if (!g) return
    const landed = simTime >= track.t[track.t.length - 1]
    g.visible = !landed
    if (!landed) g.position.set(...place(samplePath(track, simTime)))
  })

  return (
    <group>
      <Line points={lines.nominal} color="#7dd3fc" lineWidth={2} dashed dashSize={12} gapSize={8} />
      {mission.comms.map((c) => (
        <mesh key={c.step} position={place(c.position)}>
          <sphereGeometry args={[c.step === mission.outage.step ? 9 : 5, 12, 12]} />
          <meshBasicMaterial color={c.step === mission.outage.step ? '#ffffff' : COMMS_COLORS[c.state]} />
        </mesh>
      ))}
      {mission.fallbacks.map((f) => (
        <group key={f.rank}>
          <Line points={lines.fallbacks[f.rank - 1]} color={FALLBACK_COLORS[f.rank - 1]} lineWidth={f.rank === rank ? 4 : 1.5} />
          <mesh position={place(f.touchdown)}>
            <cylinderGeometry args={[8, 8, 2, 20]} />
            <meshBasicMaterial color={FALLBACK_COLORS[f.rank - 1]} />
          </mesh>
        </group>
      ))}
      <mesh position={place(mission.nominal.touchdown)}>
        <cylinderGeometry args={[8, 8, 2, 20]} />
        <meshBasicMaterial color="#7dd3fc" />
      </mesh>
      <group ref={lander}>
        <mesh>
          <coneGeometry args={[7, 14, 4]} />
          <meshStandardMaterial color="#f8fafc" emissive="#94a3b8" emissiveIntensity={0.4} />
        </mesh>
      </group>
    </group>
  )
}
