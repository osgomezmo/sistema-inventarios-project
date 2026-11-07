// Formatos de pantalla en español de Colombia. Las fechas llegan en UTC (ISO 8601)
// y se muestran en la hora de Manizales para que un movimiento nocturno no salte de día.
import type { EstadoOrden, Producto, TipoMovimiento, UnidadMedida } from '../api/types'

const ZONA = 'America/Bogota'

const pesos = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })
const pesosCompactos = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', notation: 'compact', maximumFractionDigits: 1 })
const entero = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 })
const tresDecimales = new Intl.NumberFormat('es-CO', { minimumFractionDigits: 3, maximumFractionDigits: 3 })

export const dinero = (n: number) => pesos.format(n)
export const dineroCorto = (n: number) => pesosCompactos.format(n)
export const numero = (n: number) => entero.format(n)

const abrevUnidad: Record<UnidadMedida, string> = { UNIDAD: 'und', KILO: 'kg', LITRO: 'L' }
export const unidad = (u: UnidadMedida) => abrevUnidad[u]

/** Cantidad con los decimales de su unidad: enteros por unidad, tres decimales por kilo o litro. */
export function cantidad(n: number, u: UnidadMedida, conUnidad = true): string {
  const texto = u === 'UNIDAD' ? entero.format(n) : tresDecimales.format(n)
  return conUnidad ? `${texto} ${abrevUnidad[u]}` : texto
}

export const cantidadProducto = (n: number, p: Pick<Producto, 'unidad_medida'>) => cantidad(n, p.unidad_medida)

export function fecha(iso: string): string {
  return new Intl.DateTimeFormat('es-CO', { timeZone: ZONA, day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(iso))
}

export function fechaHora(iso: string): string {
  return new Intl.DateTimeFormat('es-CO', { timeZone: ZONA, day: '2-digit', month: 'short', hour: 'numeric', minute: '2-digit' }).format(new Date(iso))
}

export function hora(iso: string): string {
  return new Intl.DateTimeFormat('es-CO', { timeZone: ZONA, hour: 'numeric', minute: '2-digit' }).format(new Date(iso))
}

/** Día local (AAAA-MM-DD) de una fecha UTC. */
export function diaLocal(iso: string): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: ZONA, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(iso))
}

export const numeroMovimiento = (id: number) => `MOV-${String(id).padStart(6, '0')}`
export const numeroTraslado = (id: number) => `TR-${String(id).padStart(4, '0')}`

export const nombreTipo: Record<TipoMovimiento, string> = {
  ENTRADA_COMPRA: 'Entrada por compra',
  AJUSTE_POSITIVO: 'Ajuste positivo',
  TRASLADO_ENTRADA: 'Traslado (entrada)',
  DEVOLUCION_CLIENTE: 'Devolución de cliente',
  SALIDA: 'Salida',
  AJUSTE_NEGATIVO: 'Ajuste negativo',
  TRASLADO_SALIDA: 'Traslado (salida)',
  DEVOLUCION_PROVEEDOR: 'Devolución a proveedor',
}

export const nombreEstadoOrden: Record<EstadoOrden, string> = {
  BORRADOR: 'Borrador',
  APROBADA: 'Aprobada',
  RECIBIDA_PARCIAL: 'Recibida parcialmente',
  RECIBIDA: 'Recibida',
  ANULADA: 'Anulada',
}
