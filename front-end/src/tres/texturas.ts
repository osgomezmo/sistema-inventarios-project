// Texturas dibujadas en canvas (sin imágenes externas): concreto, madera de estiba,
// cartón corrugado y franja de peligro.
import * as THREE from 'three'

function lienzo(ancho: number, alto: number, dibujar: (c: CanvasRenderingContext2D) => void): THREE.CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = ancho
  canvas.height = alto
  dibujar(canvas.getContext('2d')!)
  const t = new THREE.CanvasTexture(canvas)
  t.colorSpace = THREE.SRGBColorSpace
  t.anisotropy = 4
  return t
}

function semilla(n: number) {
  return () => {
    n = (n * 16807) % 2147483647
    return n / 2147483647
  }
}

let cache: Record<string, THREE.Texture> | null = null

export function texturas() {
  if (cache) return cache as {
    concreto: THREE.Texture; madera: THREE.Texture; carton: THREE.Texture; franja: THREE.Texture
  }
  const azar = semilla(7)

  const concreto = lienzo(512, 512, (c) => {
    c.fillStyle = '#cfcfca'
    c.fillRect(0, 0, 512, 512)
    for (let i = 0; i < 9000; i++) {
      const g = 180 + Math.floor(azar() * 40)
      c.fillStyle = `rgba(${g},${g},${g - 4},${0.18 + azar() * 0.2})`
      c.fillRect(azar() * 512, azar() * 512, 1 + azar() * 2, 1 + azar() * 2)
    }
    c.strokeStyle = 'rgba(120,120,115,0.35)'
    c.lineWidth = 2
    c.strokeRect(1, 1, 510, 510) // junta de dilatación de la losa
  })
  concreto.wrapS = concreto.wrapT = THREE.RepeatWrapping
  concreto.repeat.set(10, 7)

  const madera = lienzo(256, 64, (c) => {
    c.fillStyle = '#b8885a'
    c.fillRect(0, 0, 256, 64)
    for (let i = 0; i < 28; i++) {
      c.strokeStyle = `rgba(110,72,38,${0.15 + azar() * 0.25})`
      c.lineWidth = 1 + azar() * 1.5
      c.beginPath()
      const y = azar() * 64
      c.moveTo(0, y)
      c.bezierCurveTo(80, y + azar() * 6 - 3, 170, y + azar() * 6 - 3, 256, y + azar() * 4 - 2)
      c.stroke()
    }
  })

  const carton = lienzo(256, 256, (c) => {
    c.fillStyle = '#c9a06a'
    c.fillRect(0, 0, 256, 256)
    for (let i = 0; i < 2500; i++) {
      c.fillStyle = `rgba(120,85,45,${azar() * 0.12})`
      c.fillRect(azar() * 256, azar() * 256, 2, 2)
    }
    c.fillStyle = 'rgba(232,214,178,0.85)' // cinta de embalaje
    c.fillRect(112, 0, 32, 256)
    c.strokeStyle = 'rgba(80,55,25,0.55)'
    c.lineWidth = 6
    c.strokeRect(3, 3, 250, 250)
    c.strokeStyle = 'rgba(25,20,15,0.8)' // pictograma «este lado arriba»
    c.lineWidth = 5
    for (const x of [30, 62]) {
      c.beginPath()
      c.moveTo(x, 70); c.lineTo(x, 34); c.moveTo(x - 10, 46); c.lineTo(x, 34); c.lineTo(x + 10, 46)
      c.stroke()
    }
  })

  const franja = lienzo(128, 128, (c) => {
    c.fillStyle = '#ffc72c'
    c.fillRect(0, 0, 128, 128)
    c.fillStyle = '#17181b'
    for (let i = -128; i < 256; i += 32) {
      c.beginPath()
      c.moveTo(i, 0); c.lineTo(i + 16, 0); c.lineTo(i + 16 - 128, 128); c.lineTo(i - 128, 128)
      c.closePath()
      c.fill()
    }
  })
  franja.wrapS = franja.wrapT = THREE.RepeatWrapping

  cache = { concreto, madera, carton, franja }
  return cache as { concreto: THREE.Texture; madera: THREE.Texture; carton: THREE.Texture; franja: THREE.Texture }
}
