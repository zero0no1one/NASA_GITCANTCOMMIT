import { useMemo } from 'react'
import * as THREE from 'three'
import type { ThreeEvent } from '@react-three/fiber'
import type { TerrainGrid } from '../api'
import type { Layer } from '../state'
import { fromScene } from './geo'

const RAMPS: Record<Layer, [number, string][]> = {
  elevation: [[0, '#2b2b30'], [0.5, '#8a8a90'], [1, '#e8e6df']],
  hazard: [[0, '#1f9d55'], [0.4, '#d6c33a'], [0.75, '#e07b2c'], [1, '#b3263a']],
  slope: [[0, '#f4f1e8'], [0.4, '#e0b04a'], [1, '#7a1f2b']],
}

function rampColor(stops: [number, string][], v: number, out: THREE.Color) {
  const t = Math.min(1, Math.max(0, v))
  for (let i = 1; i < stops.length; i++) {
    if (t <= stops[i][0]) {
      const [p0, c0] = stops[i - 1]
      const [p1, c1] = stops[i]
      return out.set(c0).lerp(new THREE.Color(c1), (t - p0) / (p1 - p0))
    }
  }
  return out.set(stops[stops.length - 1][1])
}

interface Props {
  grid: TerrainGrid
  layer: Layer
  exaggeration: number
  onPick?: (x: number, y: number) => void
}

export function Terrain({ grid, layer, exaggeration, onPick }: Props) {
  const geometry = useMemo(() => {
    const { rows, cols, dx, dy, z, z_min, z_max, nodata } = grid
    const width = (cols - 1) * dx
    const height = (rows - 1) * dy
    const positions = new Float32Array(rows * cols * 3)
    const colors = new Float32Array(rows * cols * 3)
    const values = layer === 'hazard' ? grid.hazard : layer === 'slope' ? grid.slope : z
    const span = layer === 'elevation' ? Math.max(z_max - z_min, 1) : layer === 'slope' ? 30 : 1
    const base = layer === 'elevation' ? z_min : 0
    const color = new THREE.Color()
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const i = r * cols + c
        const elevation = z[i] === nodata ? z_min : z[i]
        positions.set([c * dx - width / 2, (elevation - z_min) * exaggeration, -(r * dy - height / 2)], i * 3)
        if (z[i] === nodata) color.set('#3a0d14')
        else rampColor(RAMPS[layer], (values[i] - base) / span, color)
        colors.set([color.r, color.g, color.b], i * 3)
      }
    }
    const index: number[] = []
    for (let r = 0; r < rows - 1; r++) {
      for (let c = 0; c < cols - 1; c++) {
        const a = r * cols + c
        const b = a + 1
        const d = a + cols
        const e = d + 1
        index.push(a, b, d, b, e, d)
      }
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    g.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    g.setIndex(index)
    g.computeVertexNormals()
    return g
  }, [grid, layer, exaggeration])

  const pick = (e: ThreeEvent<MouseEvent>) => {
    if (!onPick || e.delta > 4) return   // ignore clicks that were really camera drags
    e.stopPropagation()
    const [x, y] = fromScene(grid, e.point.x, e.point.z)
    onPick(x, y)
  }

  return (
    <mesh geometry={geometry} onClick={pick} receiveShadow>
      <meshStandardMaterial vertexColors roughness={0.95} metalness={0} side={THREE.DoubleSide} />
    </mesh>
  )
}
