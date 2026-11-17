// Rack decorativo de la pantalla de ingreso. Antes de iniciar sesión no hay token para
// leer el stock real, así que la portada dibuja un rack fijo (no son datos del sistema).
import type { Saldo } from '../api/types'
import type { CategoriaDe } from './rack'

const PILAS: Array<[categoria: string, minimo: number, cantidad: number]> = [
  ['Lácteos', 40, 52], ['Lácteos', 30, 12], ['Lácteos', 24, 66], ['Lácteos', 20, 31],
  ['Bebidas', 48, 120], ['Bebidas', 36, 74], ['Bebidas', 24, 0], ['Bebidas', 30, 41],
  ['Abarrotes', 60, 150], ['Abarrotes', 40, 55], ['Abarrotes', 25, 18], ['Abarrotes', 50, 92],
  ['Aseo', 20, 37], ['Aseo', 18, 22], ['Aseo', 16, 40],
]

export const saldosPortada: Saldo[] = PILAS.map(([, minimo, cantidad], i) => ({
  sku: `PORTADA-${String(i + 1).padStart(2, '0')}`,
  id_bodega: 1,
  cantidad,
  costo_promedio: 0,
  valor: 0,
  stock_minimo: minimo,
  bajo_minimo: cantidad <= minimo,
}))

const categoriaPorSku = new Map(saldosPortada.map((s, i) => [s.sku, PILAS[i][0]]))
export const categoriaPortada: CategoriaDe = (sku) => categoriaPorSku.get(sku) ?? 'Abarrotes'
