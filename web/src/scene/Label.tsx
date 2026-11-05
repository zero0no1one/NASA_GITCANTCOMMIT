import { useEffect, useMemo } from 'react'
import { useThree, type ThreeEvent } from '@react-three/fiber'
import * as THREE from 'three'

const FIELD_OF_VIEW_FACTOR = 0.768 // 2*tan(fov/2) at the scene's 42° field of view
const PIXEL_RATIO = 3             // labels are drawn sharper than they appear

interface DrawnLabel {
  texture: THREE.CanvasTexture
  aspect: number
}

function drawText(text: string, color: string, sizePx: number): DrawnLabel {
  const font = `500 ${sizePx * PIXEL_RATIO}px "IBM Plex Sans", system-ui, sans-serif`
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')!
  ctx.font = font
  const pad = sizePx * PIXEL_RATIO * 0.5
  canvas.width = Math.ceil(ctx.measureText(text).width + pad * 2)
  canvas.height = Math.ceil(sizePx * PIXEL_RATIO * 1.5)
  ctx.font = font
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.lineJoin = 'round'
  ctx.lineWidth = sizePx * PIXEL_RATIO * 0.32
  ctx.strokeStyle = 'rgba(0, 0, 0, 0.9)'
  ctx.strokeText(text, canvas.width / 2, canvas.height / 2)
  ctx.fillStyle = color
  ctx.fillText(text, canvas.width / 2, canvas.height / 2)
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return { texture, aspect: canvas.width / canvas.height }
}

function drawFlag(text: string, sizePx: number): DrawnLabel {
  const px = sizePx * PIXEL_RATIO
  const canvas = document.createElement('canvas')
  canvas.width = px
  canvas.height = px
  const ctx = canvas.getContext('2d')!
  ctx.beginPath()
  ctx.arc(px / 2, px / 2, px / 2 - PIXEL_RATIO * 1.2, 0, Math.PI * 2)
  ctx.fillStyle = 'rgba(0, 0, 0, 0.85)'
  ctx.fill()
  ctx.lineWidth = PIXEL_RATIO * 1.6
  ctx.strokeStyle = '#e3b341'
  ctx.stroke()
  ctx.font = `500 ${px * 0.56}px "Jost Variable", system-ui, sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillStyle = '#e3b341'
  ctx.fillText(text, px / 2, px / 2 + px * 0.03)
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return { texture, aspect: 1 }
}

interface SpriteProps {
  drawn: DrawnLabel
  heightPx: number
  position: THREE.Vector3
  renderOrder?: number
  opacity?: number
  onClick?: (e: ThreeEvent<MouseEvent>) => void
}

/** A fixed-size sprite that always faces the camera and draws over the terrain. */
function ScreenSprite({ drawn, heightPx, position, renderOrder = 10, opacity = 1, onClick }: SpriteProps) {
  const viewHeight = useThree((s) => s.size.height)
  const height = (heightPx / viewHeight) * FIELD_OF_VIEW_FACTOR
  useEffect(() => () => drawn.texture.dispose(), [drawn])
  const hover = (over: boolean) => {
    if (onClick) document.body.style.cursor = over ? 'pointer' : ''
  }
  return (
    <sprite
      position={position}
      scale={[height * drawn.aspect, height, 1]}
      renderOrder={renderOrder}
      onClick={onClick}
      onPointerOver={() => hover(true)}
      onPointerOut={() => hover(false)}
    >
      <spriteMaterial map={drawn.texture} sizeAttenuation={false} depthTest={false} depthWrite={false} transparent opacity={opacity} fog={false} />
    </sprite>
  )
}

export function TextLabel({ text, position, color = '#efebe1', sizePx = 12, opacity = 0.85 }: {
  text: string; position: THREE.Vector3; color?: string; sizePx?: number; opacity?: number
}) {
  const drawn = useMemo(() => drawText(text, color, sizePx), [text, color, sizePx])
  return <ScreenSprite drawn={drawn} heightPx={sizePx * 1.5} position={position} opacity={opacity} />
}

export function FlagLabel({ text, position, onClick }: { text: string; position: THREE.Vector3; onClick: () => void }) {
  const drawn = useMemo(() => drawFlag(text, 26), [text])
  return (
    <ScreenSprite drawn={drawn} heightPx={26} position={position} renderOrder={12} onClick={(e) => { e.stopPropagation(); onClick() }} />
  )
}
