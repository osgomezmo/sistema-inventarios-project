// Geometría y distribución del rack selectivo. Todas las bodegas usan las mismas medidas
// (módulo, altura de nivel y escala de cajas), para que las pilas se comparen sin engaño.
import * as THREE from 'three'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import type { Saldo } from '../api/types'
import { categoriaRaiz, productoPorSku } from '../api/mock/maestros'

export const MEDIDAS = {
  posicion: 1.35,      // ancho de una posición de estiba
  paral: 0.09,         // sección del paral
  fondo: 1.1,          // profundidad del marco
  nivel: 1.6,          // altura entre largueros
  larguero: 0.12,      // alto del larguero
  estibaAlto: 0.144,
  caja: { x: 0.56, y: 0.27, z: 0.46 },
  capacidadNivel: 6,   // posiciones por nivel (3 módulos de 2)
}

export const ANCHO_MODULO = MEDIDAS.posicion * 2

export interface Posicion {
  saldo: Saldo
  categoria: string
  nivel: number        // 0 = piso
  indice: number       // posición dentro del nivel
  codigo: string       // B2-N1-P03
  x: number
  y: number
  cajas: number
}

export interface Segmento { categoria: string; nivel: number; desde: number; hasta: number }

export interface DistribucionRack {
  posiciones: Posicion[]
  segmentos: Segmento[]
  niveles: number
  modulos: number
  largo: number
  alto: number
}

/** Cajas sobre la estiba: 5 cajas = el stock mínimo; 16 (cuatro capas) es el tope visual. */
export function cajasPorSaldo(cantidad: number, minimo: number): number {
  if (cantidad <= 0) return 0
  return Math.max(1, Math.min(16, Math.round((cantidad / Math.max(minimo, 1)) * 5)))
}

const xPosicion = (indice: number) => {
  const modulo = Math.floor(indice / 2)
  const lado = indice % 2
  return modulo * (ANCHO_MODULO + MEDIDAS.paral) + MEDIDAS.paral + lado * MEDIDAS.posicion + MEDIDAS.posicion / 2
}

/** Reparte los productos de la bodega en niveles: cada categoría queda contigua en un nivel. */
export function distribuir(saldos: Saldo[], codigoBodega: string): DistribucionRack {
  const porCategoria = new Map<string, Saldo[]>()
  for (const s of [...saldos].sort((a, b) => a.sku.localeCompare(b.sku))) {
    const c = categoriaRaiz(productoPorSku.get(s.sku)!.id_categoria).nombre
    porCategoria.set(c, [...(porCategoria.get(c) ?? []), s])
  }
  const grupos = [...porCategoria.entries()].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]))

  const C = MEDIDAS.capacidadNivel
  const niveles: Array<Array<[string, Saldo[]]>> = []
  for (const [categoria, lista] of grupos) {
    for (let i = 0; i < lista.length; i += C) {
      const trozo = lista.slice(i, i + C)
      const hueco = niveles.find((n) => C - n.reduce((a, [, l]) => a + l.length, 0) >= trozo.length)
      if (hueco && i === 0) hueco.push([categoria, trozo])
      else niveles.push([[categoria, trozo]])
    }
  }
  if (niveles.length === 1 && niveles[0].length > 1) niveles.push([niveles[0].pop()!])

  const posiciones: Posicion[] = []
  const segmentos: Segmento[] = []
  niveles.forEach((grupo, nivel) => {
    let indice = 0
    for (const [categoria, lista] of grupo) {
      segmentos.push({ categoria, nivel, desde: indice, hasta: indice + lista.length - 1 })
      for (const saldo of lista) {
        posiciones.push({
          saldo,
          categoria,
          nivel,
          indice,
          codigo: `${codigoBodega}-N${nivel + 1}-P${String(indice + 1).padStart(2, '0')}`,
          x: xPosicion(indice),
          y: nivel * MEDIDAS.nivel,
          cajas: cajasPorSaldo(saldo.cantidad, saldo.stock_minimo),
        })
        indice++
      }
    }
  })

  const modulos = Math.ceil(C / 2)
  return {
    posiciones,
    segmentos,
    niveles: niveles.length,
    modulos,
    largo: modulos * (ANCHO_MODULO + MEDIDAS.paral) + MEDIDAS.paral,
    alto: niveles.length * MEDIDAS.nivel + 0.1,
  }
}

export const xDe = xPosicion

// ---------- Geometrías fusionadas (una malla por pieza) ----------

const caja = (sx: number, sy: number, sz: number, x: number, y: number, z: number, rotX = 0) => {
  const g = new THREE.BoxGeometry(sx, sy, sz)
  if (rotX) g.rotateX(rotX)
  g.translate(x, y, z)
  return g
}

let estibaCache: THREE.BufferGeometry | null = null
/** Estiba de madera: 5 tablas arriba, 3 largueros de taco y 3 tablas abajo. */
export function geometriaEstiba(): THREE.BufferGeometry {
  if (estibaCache) return estibaCache
  const piezas: THREE.BufferGeometry[] = []
  const ancho = 1.2, fondo = 1.0
  for (let i = 0; i < 5; i++) piezas.push(caja(ancho, 0.022, 0.14, 0, 0.133, -fondo / 2 + 0.07 + i * ((fondo - 0.14) / 4)))
  for (let i = 0; i < 3; i++) piezas.push(caja(0.1, 0.1, fondo, -ancho / 2 + 0.05 + i * ((ancho - 0.1) / 2), 0.072, 0))
  for (let i = 0; i < 3; i++) piezas.push(caja(ancho, 0.022, 0.14, 0, 0.011, -fondo / 2 + 0.07 + i * ((fondo - 0.14) / 2)))
  estibaCache = mergeGeometries(piezas)!
  return estibaCache
}

const cajasCache = new Map<number, THREE.BufferGeometry>()
/** n cajas apiladas en capas de 2 × 2 sobre la estiba. */
export function geometriaCajas(n: number): THREE.BufferGeometry | null {
  if (n <= 0) return null
  if (cajasCache.has(n)) return cajasCache.get(n)!
  const { x, y, z } = MEDIDAS.caja
  const piezas: THREE.BufferGeometry[] = []
  for (let i = 0; i < n; i++) {
    const capa = Math.floor(i / 4)
    const lugar = i % 4
    piezas.push(caja(x, y, z, ((lugar % 2) - 0.5) * (x + 0.02), MEDIDAS.estibaAlto + capa * (y + 0.005) + y / 2, (Math.floor(lugar / 2) - 0.5) * (z + 0.02)))
  }
  const g = mergeGeometries(piezas)!
  cajasCache.set(n, g)
  return g
}

/** Parales y arriostramiento (azul) y largueros (naranja) del rack completo. */
export function geometriaRack(d: DistribucionRack) {
  const { paral, fondo, nivel, larguero } = MEDIDAS
  const altoParal = d.niveles * nivel + 0.1
  const parales: THREE.BufferGeometry[] = []
  const largueros: THREE.BufferGeometry[] = []
  const protectores: Array<[number, number]> = []

  for (let m = 0; m <= d.modulos; m++) {
    const x = m * (ANCHO_MODULO + paral) + paral / 2
    for (const z of [fondo / 2 - paral / 2, -fondo / 2 + paral / 2]) parales.push(caja(paral, altoParal, paral, x, altoParal / 2, z))
    // arriostramiento en zigzag del marco lateral
    const tramos = Math.max(2, Math.round(altoParal / 0.9))
    const paso = altoParal / tramos
    const largo = Math.hypot(paso, fondo - paral)
    const angulo = Math.atan2(paso, fondo - paral)
    for (let t = 0; t < tramos; t++) {
      parales.push(caja(0.03, 0.03, largo, x, paso * t + paso / 2, 0, t % 2 ? angulo : -angulo))
      parales.push(caja(0.03, 0.03, fondo - paral, x, paso * t, 0))
    }
    protectores.push([x, fondo / 2 + 0.02])
  }
  for (let n = 1; n <= d.niveles; n++) {
    for (let m = 0; m < d.modulos; m++) {
      const x0 = m * (ANCHO_MODULO + paral) + paral
      for (const z of [fondo / 2 - 0.03, -fondo / 2 + 0.03]) largueros.push(caja(ANCHO_MODULO, larguero, 0.05, x0 + ANCHO_MODULO / 2, n * nivel - larguero / 2, z))
    }
  }
  return { parales: mergeGeometries(parales)!, largueros: mergeGeometries(largueros)!, protectores, altoParal }
}
