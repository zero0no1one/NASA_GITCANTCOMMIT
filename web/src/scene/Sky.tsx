import { useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { Stars } from '@react-three/drei'
import * as THREE from 'three'

// Seen from the Moon, Earth is about 1.9° wide and the Sun about 0.53°: both drawn at true size.
const EARTH_RADIUS_DEG = 0.95
const SUN_RADIUS_DEG = 0.265

function earthTexture() {
  const size = 512
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size / 2
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#123f7a'
  ctx.fillRect(0, 0, size, size / 2)
  // Land and cloud as soft blotches: enough to read as Earth at this size, not a real map.
  let seed = 7
  const random = () => (seed = (seed * 16807) % 2147483647) / 2147483647
  for (let i = 0; i < 90; i++) {
    ctx.fillStyle = `rgba(${90 + random() * 60}, ${110 + random() * 40}, ${70 + random() * 30}, 0.55)`
    ctx.beginPath()
    ctx.ellipse(random() * size, 40 + random() * (size / 2 - 80), 6 + random() * 30, 3 + random() * 16, random() * 3, 0, 7)
    ctx.fill()
  }
  for (let i = 0; i < 220; i++) {
    ctx.fillStyle = `rgba(255, 255, 255, ${0.15 + random() * 0.45})`
    ctx.beginPath()
    ctx.ellipse(random() * size, random() * (size / 2), 4 + random() * 34, 1 + random() * 6, random() * 0.6 - 0.3, 0, 7)
    ctx.fill()
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

function glowTexture() {
  const size = 256
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')!
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  g.addColorStop(0, 'rgba(255,255,250,1)')
  g.addColorStop(0.06, 'rgba(255,255,250,1)')
  g.addColorStop(0.09, 'rgba(255,245,225,0.45)')
  g.addColorStop(0.3, 'rgba(255,235,200,0.08)')
  g.addColorStop(1, 'rgba(255,235,200,0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, size, size)
  return new THREE.CanvasTexture(canvas)
}

/** Stars, plus the Earth and Sun at their true positions and sizes, kept infinitely far from the camera. */
export function Sky({ span, sun, earth }: { span: number; sun: [number, number, number]; earth: [number, number, number] }) {
  const distance = span * 40
  const camera = useThree((s) => s.camera)
  const earthRef = useRef<THREE.Mesh>(null)
  const sunRef = useRef<THREE.Sprite>(null)
  const earthMap = useMemo(() => earthTexture(), [])
  const glow = useMemo(() => glowTexture(), [])
  const sunVector = useMemo(() => new THREE.Vector3(...sun), [sun])
  const earthVector = useMemo(() => new THREE.Vector3(...earth), [earth])

  useFrame(() => {
    earthRef.current?.position.copy(camera.position).addScaledVector(earthVector, distance)
    sunRef.current?.position.copy(camera.position).addScaledVector(sunVector, distance)
  })

  const earthRadius = distance * Math.tan((EARTH_RADIUS_DEG * Math.PI) / 180)
  // The bright disc is 0.06 of the sprite's half-width, so scale the sprite to put the disc at true size.
  const sunSprite = (distance * Math.tan((SUN_RADIUS_DEG * Math.PI) / 180) * 2) / 0.12

  return (
    <group>
      <Stars radius={distance * 0.9} depth={distance * 0.05} count={6000} factor={span / 28} saturation={0} fade={false} />
      <mesh ref={earthRef} rotation={[0.4, 2.2, 0]}>
        <sphereGeometry args={[earthRadius, 48, 32]} />
        <meshStandardMaterial map={earthMap} roughness={0.75} fog={false} emissive="#79b4ff" emissiveIntensity={0.03} />
      </mesh>
      <sprite ref={sunRef} scale={[sunSprite, sunSprite, 1]}>
        <spriteMaterial map={glow} blending={THREE.AdditiveBlending} depthWrite={false} transparent fog={false} />
      </sprite>
    </group>
  )
}
