import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Line } from '@react-three/drei'
import * as THREE from 'three'
import type { LandingSite, TerrainGrid } from '../api'
import { groundVerdict, latLon, sampleField, toLocal } from '../coords'
import { useSim } from '../state'
import { toScene } from './geo'
import { FlagLabel, TextLabel } from './Label'

const LIFT = 1.2 // lines sit just above the ground so they don't flicker into it

function draped(grid: TerrainGrid, exaggeration: number, x: number, y: number) {
  const z = sampleField(grid, 'z', x, y) ?? grid.z_min
  const [a, b, c] = toScene(grid, exaggeration, x, y, z)
  return new THREE.Vector3(a, b + LIFT, c)
}

const niceSteps = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10]

function niceStep(span: number) {
  return niceSteps.find((s) => span / s <= 5) ?? 10
}

interface GridLine {
  key: string
  points: THREE.Vector3[]
  label: string
  at: THREE.Vector3
}

/** Real latitude and longitude lines laid over the terrain, or a metre grid on test terrain. */
export function Graticule({ grid, exaggeration }: { grid: TerrainGrid; exaggeration: number }) {
  const lines = useMemo<GridLine[]>(() => {
    const width = (grid.cols - 1) * grid.dx
    const height = (grid.rows - 1) * grid.dy
    const out: GridLine[] = []
    const inside = (x: number, y: number) => x >= 0 && y >= 0 && x <= width && y <= height

    const trace = (key: string, label: string, at: (t: number) => [number, number] | null) => {
      const points: THREE.Vector3[] = []
      for (let i = 0; i <= 80; i++) {
        const p = at(i / 80)
        if (p && inside(p[0], p[1])) points.push(draped(grid, exaggeration, p[0], p[1]))
      }
      if (points.length > 3) out.push({ key, points, label, at: points[points.length - 1] })
    }

    if (!grid.origin_xy) {
      for (let x = 200; x < width; x += 200) trace(`x${x}`, `${x} m E`, (t) => [x, t * height])
      for (let y = 200; y < height; y += 200) trace(`y${y}`, `${y} m N`, (t) => [t * width, y])
      return out
    }
    const corners = [[0, 0], [width, 0], [0, height], [width, height]].map(([x, y]) => latLon(grid, x, y)!)
    const lats = corners.map((c) => c[0])
    const lons = corners.map((c) => c[1])
    const [latLow, latHigh] = [Math.min(...lats), Math.max(...lats)]
    const [lonLow, lonHigh] = [Math.min(...lons), Math.max(...lons)]
    const latStep = niceStep(latHigh - latLow)
    const lonStep = niceStep(lonHigh - lonLow)
    const digits = (step: number) => (step >= 1 ? 0 : step >= 0.1 ? 1 : step >= 0.01 ? 2 : 3)
    for (let lat = Math.ceil(latLow / latStep) * latStep; lat <= latHigh; lat += latStep) {
      trace(`lat${lat.toFixed(4)}`, `${Math.abs(lat).toFixed(digits(latStep))}° S`,
        (t) => toLocal(grid, lat, lonLow + t * (lonHigh - lonLow)))
    }
    for (let lon = Math.ceil(lonLow / lonStep) * lonStep; lon <= lonHigh; lon += lonStep) {
      trace(`lon${lon.toFixed(4)}`, `${Math.abs(lon).toFixed(digits(lonStep))}° ${lon < 0 ? 'W' : 'E'}`,
        (t) => toLocal(grid, latLow + t * (latHigh - latLow), lon))
    }
    return out
  }, [grid, exaggeration])

  const outline = useMemo(() => {
    const width = (grid.cols - 1) * grid.dx
    const height = (grid.rows - 1) * grid.dy
    const steps = 60
    const points: THREE.Vector3[] = []
    for (let i = 0; i <= steps; i++) points.push(draped(grid, exaggeration, (i / steps) * width, 0))
    for (let i = 0; i <= steps; i++) points.push(draped(grid, exaggeration, width, (i / steps) * height))
    for (let i = 0; i <= steps; i++) points.push(draped(grid, exaggeration, width - (i / steps) * width, height))
    for (let i = 0; i <= steps; i++) points.push(draped(grid, exaggeration, 0, height - (i / steps) * height))
    return points
  }, [grid, exaggeration])

  return (
    <group>
      <Line points={outline} color="#efebe1" lineWidth={1} transparent opacity={0.55} />
      {lines.map((l) => (
        <group key={l.key}>
          <Line points={l.points} color="#efebe1" lineWidth={0.75} transparent opacity={0.28} />
          <TextLabel text={l.label} position={l.at} />
        </group>
      ))}
    </group>
  )
}

/** A landing-point reticle, after the grid etched on the Apollo Lunar Module window. */
function reticleGeometry(radius: number) {
  const points: number[] = []
  const arcs = 4
  for (let a = 0; a < arcs; a++) {
    const start = (a / arcs) * Math.PI * 2 + 0.22
    const end = start + (Math.PI * 2) / arcs - 0.44
    for (let i = 0; i < 16; i++) {
      const t0 = start + ((end - start) * i) / 16
      const t1 = start + ((end - start) * (i + 1)) / 16
      points.push(Math.cos(t0) * radius, 0, Math.sin(t0) * radius, Math.cos(t1) * radius, 0, Math.sin(t1) * radius)
    }
  }
  for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
    points.push(dx * radius * 0.55, 0, dz * radius * 0.55, dx * radius * 1.45, 0, dz * radius * 1.45)
  }
  const g = new THREE.BufferGeometry()
  g.setAttribute('position', new THREE.Float32BufferAttribute(points, 3))
  return g
}

/** Follows the cursor over the terrain, coloured by whether that ground could be landed on. */
export function HoverReticle({ grid, exaggeration }: { grid: TerrainGrid; exaggeration: number }) {
  const span = Math.max((grid.cols - 1) * grid.dx, (grid.rows - 1) * grid.dy)
  const geometry = useMemo(() => reticleGeometry(span * 0.018), [span])
  const ref = useRef<THREE.LineSegments>(null)
  const material = useRef<THREE.LineBasicMaterial>(null)
  useFrame(() => {
    const { hover } = useSim.getState()
    const obj = ref.current
    if (!obj || !material.current) return
    obj.visible = hover !== null
    if (!hover) return
    obj.position.copy(draped(grid, exaggeration, hover[0], hover[1]))
    obj.position.y += 1
    material.current.color.set(groundVerdict(grid, hover[0], hover[1]).ok ? '#8fd9b6' : '#ff7a45')
  })
  return (
    <lineSegments ref={ref} geometry={geometry} visible={false}>
      <lineBasicMaterial ref={material} depthTest={false} transparent />
    </lineSegments>
  )
}

/** A fixed marker on the ground: the landing target, inspected spot or rover goal. */
export function GroundMark({ grid, exaggeration, at, color, scale = 1 }: {
  grid: TerrainGrid; exaggeration: number; at: [number, number]; color: string; scale?: number
}) {
  const span = Math.max((grid.cols - 1) * grid.dx, (grid.rows - 1) * grid.dy)
  const geometry = useMemo(() => reticleGeometry(span * 0.018 * scale), [span, scale])
  const position = useMemo(() => draped(grid, exaggeration, at[0], at[1]), [grid, exaggeration, at])
  return (
    <lineSegments geometry={geometry} position={position}>
      <lineBasicMaterial color={color} depthTest={false} transparent />
    </lineSegments>
  )
}

/** Ranked landing sites as numbered flags planted on the terrain. */
export function SiteFlags({ grid, exaggeration, sites, onPick }: {
  grid: TerrainGrid; exaggeration: number; sites: LandingSite[]; onPick: (site: LandingSite) => void
}) {
  const span = Math.max((grid.cols - 1) * grid.dx, (grid.rows - 1) * grid.dy)
  return (
    <group>
      {sites.map((site, i) => {
        const base = draped(grid, exaggeration, site.x_m, site.y_m)
        const top = base.clone().setY(base.y + span * 0.05)
        return (
          <group key={`${site.x_m},${site.y_m}`}>
            <Line points={[base, top]} color="#e3b341" lineWidth={1.25} />
            <FlagLabel text={String(i + 1)} position={top} onClick={() => onPick(site)} />
          </group>
        )
      })}
    </group>
  )
}
