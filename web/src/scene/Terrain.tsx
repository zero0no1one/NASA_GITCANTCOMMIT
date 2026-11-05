import { useMemo } from 'react'
import * as THREE from 'three'
import type { HorizonGrid, TerrainGrid } from '../api'
import type { Layer } from '../state'

const RAMPS: Partial<Record<Layer, [number, string][]>> = {
  safety: [[0, '#6fd8a8'], [0.45, '#e6d36a'], [0.85, '#ff9a4a'], [1, '#ff5a2c']],
  slope: [[0, '#b9b5ab'], [0.4, '#e3b341'], [1, '#ff5a2c']],
  elevation: [[0, '#1d2733'], [0.5, '#7a8590'], [1, '#f2ede2']],
}

const scratch = new THREE.Color()

function rampColor(stops: [number, string][], v: number, out: THREE.Color) {
  const t = Math.min(1, Math.max(0, v))
  for (let i = 1; i < stops.length; i++) {
    if (t <= stops[i][0]) {
      const [p0, c0] = stops[i - 1]
      const [p1, c1] = stops[i]
      return out.set(c0).lerp(scratch.set(c1), (t - p0) / (p1 - p0))
    }
  }
  return out.set(stops[stops.length - 1][1])
}

/** Regolith: neutral grey with broad, soft variation, so bare ground never looks like flat plastic. */
function regolith(x: number, y: number, out: THREE.Color) {
  const broad = Math.sin(x * 0.011 + Math.sin(y * 0.007) * 1.7) * Math.cos(y * 0.013 + Math.sin(x * 0.005) * 2.1)
  const v = 0.2 + 0.035 * broad
  return out.setRGB(v * 1.02, v, v * 0.97)
}

/** Fine grain added per pixel, tied to the ground so it stays put as the camera moves. */
function addGrain(shader: THREE.WebGLProgramParametersWithUniforms) {
  shader.vertexShader = shader.vertexShader
    .replace('#include <common>', '#include <common>\nvarying vec3 vGround;')
    .replace('#include <begin_vertex>', '#include <begin_vertex>\nvGround = position;')
  shader.fragmentShader = shader.fragmentShader
    .replace('#include <common>', `#include <common>
      varying vec3 vGround;
      float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float smoothNoise(vec2 p) {
        vec2 i = floor(p); vec2 f = fract(p); vec2 u = f*f*(3.0-2.0*f);
        return mix(mix(hash(i), hash(i+vec2(1,0)), u.x), mix(hash(i+vec2(0,1)), hash(i+vec2(1,1)), u.x), u.y);
      }`)
    .replace('#include <color_fragment>', `#include <color_fragment>
      float grain = 0.5*smoothNoise(vGround.xz*0.09) + 0.3*smoothNoise(vGround.xz*0.37) + 0.2*smoothNoise(vGround.xz*1.7);
      diffuseColor.rgb *= 0.72 + 0.56*grain;`)
}

interface Props {
  grid: TerrainGrid
  layer: Layer
  exaggeration: number
}

/** The landing area itself: real elevations at full resolution, lit by the Sun and casting real shadows. */
export function Terrain({ grid, layer, exaggeration }: Props) {
  const geometry = useMemo(() => {
    const { rows, cols, dx, dy, z, z_min, z_max, nodata } = grid
    const width = (cols - 1) * dx
    const height = (rows - 1) * dy
    const positions = new Float32Array(rows * cols * 3)
    const colors = new Float32Array(rows * cols * 3)
    const ramp = RAMPS[layer]
    const values = layer === 'safety' ? grid.hazard : layer === 'slope' ? grid.slope : z
    const span = layer === 'elevation' ? Math.max(z_max - z_min, 1) : layer === 'slope' ? 30 : 1
    const base = layer === 'elevation' ? z_min : 0
    const color = new THREE.Color()
    const tint = new THREE.Color()
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const i = r * cols + c
        const elevation = z[i] === nodata ? z_min : z[i]
        const x = c * dx
        const y = r * dy
        positions.set([x - width / 2, (elevation - z_min) * exaggeration, -(y - height / 2)], i * 3)
        regolith(x, y, color)
        if (ramp && z[i] !== nodata) {
          // The surface stays visible under a data layer: shadows and relief still read.
          rampColor(ramp, (values[i] - base) / span, tint)
          color.lerp(tint, 0.62)
        }
        colors.set([color.r, color.g, color.b], i * 3)
      }
    }
    const index = new Uint32Array((rows - 1) * (cols - 1) * 6)
    let n = 0
    for (let r = 0; r < rows - 1; r++) {
      for (let c = 0; c < cols - 1; c++) {
        const a = r * cols + c
        index.set([a, a + 1, a + cols, a + 1, a + cols + 1, a + cols], n)
        n += 6
      }
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    g.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    g.setIndex(new THREE.BufferAttribute(index, 1))
    g.computeVertexNormals()
    return g
  }, [grid, layer, exaggeration])

  return (
    <mesh geometry={geometry} castShadow receiveShadow>
      <meshStandardMaterial vertexColors roughness={1} metalness={0} onBeforeCompile={addGrain} shadowSide={THREE.DoubleSide} />
    </mesh>
  )
}

/** NASA's surrounding terrain, thinned, so the landing area sits in a real landscape with a real horizon. */
export function Horizon({ grid, horizon, exaggeration }: { grid: TerrainGrid; horizon: HorizonGrid; exaggeration: number }) {
  const geometry = useMemo(() => {
    const { rows, cols, dx, dy, x0, y0, z, nodata } = horizon
    const width = (grid.cols - 1) * grid.dx
    const height = (grid.rows - 1) * grid.dy
    const positions = new Float32Array(rows * cols * 3)
    const colors = new Float32Array(rows * cols * 3)
    const color = new THREE.Color()
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const i = r * cols + c
        const x = x0 + c * dx
        const y = y0 + r * dy
        // Tucked under the detailed crop, so the two surfaces never fight for the same pixels.
        const under = x > -dx && x < width + dx && y > -dy && y < height + dy ? 25 : 0
        const elevation = (z[i] === nodata ? grid.z_min : z[i]) - grid.z_min
        positions.set([x - width / 2, elevation * exaggeration - under, -(y - height / 2)], i * 3)
        regolith(x, y, color)
        colors.set([color.r, color.g, color.b], i * 3)
      }
    }
    const index = new Uint32Array((rows - 1) * (cols - 1) * 6)
    let n = 0
    for (let r = 0; r < rows - 1; r++) {
      for (let c = 0; c < cols - 1; c++) {
        const a = r * cols + c
        index.set([a, a + 1, a + cols, a + 1, a + cols + 1, a + cols], n)
        n += 6
      }
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    g.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    g.setIndex(new THREE.BufferAttribute(index, 1))
    g.computeVertexNormals()
    return g
  }, [grid, horizon, exaggeration])

  return (
    <mesh geometry={geometry}>
      <meshStandardMaterial vertexColors roughness={1} metalness={0} onBeforeCompile={addGrain} />
    </mesh>
  )
}
