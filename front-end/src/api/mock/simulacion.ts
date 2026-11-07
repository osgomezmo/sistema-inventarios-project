// Simula octubre de 2026 en el supermercado de ejemplo: inventario inicial, salidas
// diarias por cierre del POS, recepciones de órdenes de compra, mermas, traslados y
// devoluciones. Cada saldo sale de sus movimientos con costo promedio ponderado,
// como lo calcula ms-inventario, así que kardex, stock, dashboard y alertas cuadran.
import type {
  DetalleOrden, DevolucionProveedor, EstadoOrden, Movimiento, Notificacion, OrdenCompra,
  Recepcion, Saldo, TipoMovimiento, Traslado,
} from '../types'
import { bodegaPorId, productoPorSku, productosPorProveedor } from './maestros'

// ---------- Utilidades ----------

function mulberry32(semilla: number) {
  return () => {
    semilla = (semilla + 0x6d2b79f5) | 0
    let t = Math.imul(semilla ^ (semilla >>> 15), 1 | semilla)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
const azar = mulberry32(20261029)
/** Generador aparte para las horas: cambiar las horas no altera las cantidades del mes. */
const azarHora = mulberry32(1029)

/** Fecha local de Manizales (UTC−5) de octubre de 2026, devuelta en ISO 8601 UTC. */
export function fechaOct(dia: number, hora: number, minuto = 0): string {
  return new Date(Date.UTC(2026, 9, dia, hora + 5, minuto)).toISOString().replace('.000Z', 'Z')
}

/** "Ahora" en la plantilla: 29/10/2026 a las 4:00 p. m. en Manizales. */
export const AHORA = fechaOct(29, 16)

const decimales = (sku: string) => (productoPorSku.get(sku)!.unidad_medida === 'UNIDAD' ? 0 : 3)
const redondear = (n: number, d: number) => Math.round(n * 10 ** d) / 10 ** d
const clave = (sku: string, id_bodega: number) => `${sku}|${id_bodega}`
const ENTRADAS: TipoMovimiento[] = ['ENTRADA_COMPRA', 'AJUSTE_POSITIVO', 'TRASLADO_ENTRADA', 'DEVOLUCION_CLIENTE']
export const esEntrada = (tipo: TipoMovimiento) => ENTRADAS.includes(tipo)
const JEFE: Record<number, number> = { 1: 3, 2: 2, 3: 3 }

// ---------- Estado vivo (lo que guarda ms-inventario) ----------

export const estadoSaldos = new Map<string, { cantidad: number; costo: number }>()
export const movimientos: Movimiento[] = []
export const traslados: Traslado[] = []
export const notificaciones: Notificacion[] = []
const alertados = new Set<string>()
let siguienteMovimiento = 2801
let siguienteNotificacion = 1

interface Intento {
  fecha: string
  sku: string
  id_bodega: number
  tipo: TipoMovimiento
  cantidad: number
  costo?: number
  motivo: string | null
  documento: string | null
  usuario: number
}

/** Aplica un movimiento con las reglas de ms-inventario. Devuelve null si no hay saldo para una salida. */
export function aplicarMovimiento(i: Intento): Movimiento | null {
  const k = clave(i.sku, i.id_bodega)
  const s = estadoSaldos.get(k) ?? { cantidad: 0, costo: 0 }
  const d = decimales(i.sku)
  const p = productoPorSku.get(i.sku)!
  const antes = s.cantidad
  let cantidad = redondear(i.cantidad, d)
  let costoUnitario: number

  if (esEntrada(i.tipo)) {
    costoUnitario = i.costo ?? s.costo
    const total = s.cantidad + cantidad
    s.costo = redondear(total > 0 ? (s.cantidad * s.costo + cantidad * costoUnitario) / total : costoUnitario, 4)
    s.cantidad = redondear(total, d)
  } else {
    cantidad = redondear(Math.min(cantidad, s.cantidad), d)
    if (cantidad <= 0) return null
    costoUnitario = s.costo
    s.cantidad = redondear(s.cantidad - cantidad, d)
  }
  estadoSaldos.set(k, s)

  const mov: Movimiento = {
    id_movimiento: siguienteMovimiento++,
    sku: i.sku,
    id_bodega: i.id_bodega,
    tipo: i.tipo,
    cantidad,
    costo_unitario: redondear(costoUnitario, 4),
    saldo_resultante: s.cantidad,
    costo_promedio: s.costo,
    valor_resultante: redondear(s.cantidad * s.costo, 2),
    motivo: i.motivo,
    documento_referencia: i.documento,
    id_usuario: i.usuario,
    fecha: i.fecha,
  }
  movimientos.push(mov)

  // StockBajoUmbral: se publica cuando un movimiento deja el saldo en el mínimo o por debajo.
  if (antes > p.stock_minimo && s.cantidad <= p.stock_minimo && !alertados.has(k)) {
    alertados.add(k)
    const b = bodegaPorId.get(i.id_bodega)!
    const agotado = s.cantidad === 0
    for (const rol of ['COMPRAS', 'JEFE_BODEGA'] as const) {
      notificaciones.push({
        id: `ntf-${String(siguienteNotificacion++).padStart(4, '0')}`,
        titulo: agotado ? `${p.nombre} agotado en ${b.codigo}` : `Stock bajo: ${p.nombre}`,
        mensaje: `${b.nombre} quedó con ${s.cantidad} y el mínimo es ${p.stock_minimo}.`,
        rol_destino: rol,
        leida: i.fecha < fechaOct(27, 0),
        fecha: i.fecha,
        sku: i.sku,
        id_bodega: i.id_bodega,
      })
    }
  }
  if (s.cantidad > p.stock_minimo) alertados.delete(k)
  return mov
}

// ---------- Ubicaciones: [sku, bodega, inventario inicial, salida diaria promedio] ----------

const ubicaciones: Array<[string, number, number, number]> = [
  ['ABA-0112', 1, 600, 16], ['ABA-0118', 1, 300, 8], ['ABA-0131', 1, 360, 9], ['ABA-0204', 1, 160, 3.6],
  ['ABA-0310', 1, 280, 6], ['ABA-0322', 1, 200, 4], ['BEB-0044', 1, 1200, 45], ['BEB-0120', 1, 600, 18],
  ['BEB-0207', 1, 220, 7], ['ASE-0207', 1, 180, 4], ['ASE-0450', 1, 90, 0.6], ['ASE-0512', 1, 220, 6],
  ['CUI-0018', 1, 260, 6], ['CUI-0103', 1, 140, 3], ['FRU-0052', 1, 900, 40], ['FRU-0044', 1, 300, 14],
  ['ABA-0112', 2, 300, 15], ['ABA-0118', 2, 180, 5], ['ABA-0204', 2, 120, 2.5], ['ABA-0310', 2, 200, 4],
  ['LAC-0001', 2, 900, 60], ['LAC-0014', 2, 500, 30], ['LAC-0102', 2, 150, 5], ['FRU-0031', 2, 600, 24],
  ['FRU-0067', 2, 120, 2.5], ['BEB-0044', 2, 1000, 22], ['BEB-0120', 2, 420, 11], ['ASE-0207', 2, 140, 4],
  ['ASE-0512', 2, 160, 3], ['CUI-0018', 2, 150, 2.5],
  ['LAC-0001', 3, 600, 0], ['LAC-0102', 3, 140, 1.5], ['LAC-0201', 3, 140, 3], ['CAR-0010', 3, 180, 7],
  ['CAR-0105', 3, 220, 9], ['FRU-0067', 3, 80, 0],
]

// ---------- Órdenes de compra (ms-compras) ----------

interface DefOrden {
  id: number
  proveedor: number
  bodega: number
  creada: number
  aprobada?: number
  anulada?: { dia: number; motivo: string }
  items: Array<[string, number]>
  recepciones?: Array<{ dia: number; hora: number; items: Array<[string, number]>; observaciones: string }>
  devoluciones?: Array<{ dia: number; items: Array<[string, number]>; motivo: string }>
}

const defOrdenes: DefOrden[] = [
  { id: 5, proveedor: 2, bodega: 2, creada: 3, aprobada: 3, items: [['LAC-0001', 480], ['LAC-0014', 240]], recepciones: [{ dia: 6, hora: 7, items: [['LAC-0001', 480], ['LAC-0014', 240]], observaciones: 'Recibido completo y en cadena de frío.' }] },
  { id: 6, proveedor: 8, bodega: 1, creada: 4, anulada: { dia: 5, motivo: 'El proveedor no sostuvo el precio cotizado.' }, items: [['CUI-0018', 120], ['CUI-0103', 60]] },
  { id: 7, proveedor: 1, bodega: 1, creada: 5, aprobada: 6, items: [['ABA-0112', 600], ['ABA-0118', 200], ['ABA-0131', 250]], recepciones: [{ dia: 8, hora: 9, items: [['ABA-0112', 600], ['ABA-0118', 200], ['ABA-0131', 250]], observaciones: 'Sin novedad.' }] },
  { id: 8, proveedor: 3, bodega: 3, creada: 7, aprobada: 7, items: [['CAR-0010', 120], ['CAR-0105', 150]], recepciones: [{ dia: 9, hora: 6, items: [['CAR-0010', 120], ['CAR-0105', 150]], observaciones: 'Temperatura de llegada 3 °C.' }] },
  { id: 9, proveedor: 4, bodega: 1, creada: 8, aprobada: 8, items: [['FRU-0052', 500], ['FRU-0044', 200]], recepciones: [{ dia: 10, hora: 6, items: [['FRU-0052', 500], ['FRU-0044', 200]], observaciones: 'Pesado en báscula de muelle.' }] },
  { id: 10, proveedor: 2, bodega: 2, creada: 10, aprobada: 11, items: [['LAC-0001', 480], ['LAC-0014', 240], ['LAC-0102', 60]], recepciones: [{ dia: 13, hora: 7, items: [['LAC-0001', 480], ['LAC-0014', 240], ['LAC-0102', 60]], observaciones: 'Sin novedad.' }] },
  { id: 11, proveedor: 5, bodega: 1, creada: 12, aprobada: 13, items: [['BEB-0044', 900], ['BEB-0120', 360], ['BEB-0207', 120]], recepciones: [{ dia: 15, hora: 10, items: [['BEB-0044', 900], ['BEB-0120', 360]], observaciones: 'El proveedor despachó sin el jugo de naranja por falta de producto.' }] },
  { id: 12, proveedor: 6, bodega: 1, creada: 13, aprobada: 14, items: [['ASE-0207', 90], ['ASE-0512', 160]], recepciones: [{ dia: 16, hora: 11, items: [['ASE-0207', 90], ['ASE-0512', 160]], observaciones: 'Seis garrafas llegaron con el envase roto.' }], devoluciones: [{ dia: 20, items: [['ASE-0207', 6]], motivo: 'Envases rotos en el transporte.' }] },
  { id: 13, proveedor: 2, bodega: 2, creada: 17, aprobada: 18, items: [['LAC-0001', 480], ['LAC-0014', 240]], recepciones: [{ dia: 20, hora: 7, items: [['LAC-0001', 480], ['LAC-0014', 240]], observaciones: 'Sin novedad.' }] },
  { id: 14, proveedor: 4, bodega: 1, creada: 20, aprobada: 20, items: [['FRU-0052', 500], ['FRU-0044', 200]], recepciones: [{ dia: 22, hora: 6, items: [['FRU-0052', 500], ['FRU-0044', 200]], observaciones: 'Pesado en báscula de muelle.' }] },
  { id: 15, proveedor: 1, bodega: 2, creada: 26, aprobada: 27, items: [['ABA-0112', 360], ['ABA-0118', 120]] },
  { id: 16, proveedor: 2, bodega: 2, creada: 24, aprobada: 25, items: [['LAC-0001', 480], ['LAC-0014', 240], ['LAC-0102', 60]], recepciones: [{ dia: 27, hora: 7, items: [['LAC-0001', 480], ['LAC-0014', 240], ['LAC-0102', 60]], observaciones: 'Sin novedad.' }] },
  { id: 17, proveedor: 7, bodega: 1, creada: 28, items: [['ABA-0204', 60], ['ABA-0310', 80], ['ABA-0322', 40]] },
  { id: 18, proveedor: 4, bodega: 2, creada: 28, aprobada: 28, items: [['FRU-0031', 400], ['FRU-0067', 60]], recepciones: [{ dia: 29, hora: 15, items: [['FRU-0067', 60]], observaciones: 'Llegó el aguacate; el banano queda pendiente para mañana.' }] },
  { id: 19, proveedor: 5, bodega: 2, creada: 29, items: [['BEB-0044', 480], ['BEB-0120', 240]] },
  // Reposición de la bodega Norte durante el mes
  { id: 20, proveedor: 1, bodega: 2, creada: 11, aprobada: 11, items: [['ABA-0112', 150]], recepciones: [{ dia: 13, hora: 9, items: [['ABA-0112', 150]], observaciones: 'Sin novedad.' }] },
  { id: 21, proveedor: 6, bodega: 2, creada: 14, aprobada: 15, items: [['ASE-0512', 80]], recepciones: [{ dia: 17, hora: 11, items: [['ASE-0512', 80]], observaciones: 'Sin novedad.' }] },
  { id: 22, proveedor: 7, bodega: 2, creada: 15, aprobada: 15, items: [['ABA-0204', 50], ['ABA-0310', 90]], recepciones: [{ dia: 18, hora: 10, items: [['ABA-0204', 50], ['ABA-0310', 90]], observaciones: 'Sin novedad.' }] },
  { id: 23, proveedor: 5, bodega: 2, creada: 16, aprobada: 16, items: [['BEB-0044', 500]], recepciones: [{ dia: 19, hora: 8, items: [['BEB-0044', 500]], observaciones: 'Sin novedad.' }] },
]

const precioCompra = (proveedor: number, sku: string) =>
  productosPorProveedor[proveedor]?.find((x) => x.sku === sku)?.precio_compra ?? Math.round(productoPorSku.get(sku)!.precio_venta * 0.7)

// ---------- Construcción de los intentos del mes ----------

const intentos: Intento[] = []
const trasladosDef: Array<{ id: number; dia: number; hora: number; minuto: number; sku: string; origen: number; destino: number; cantidad: number; motivo: string; usuario: number }> = [
  { id: 41, dia: 18, hora: 10, minuto: 20, sku: 'LAC-0001', origen: 3, destino: 2, cantidad: 120, motivo: 'Reposición de la bodega de despacho.', usuario: 3 },
  { id: 42, dia: 21, hora: 9, minuto: 40, sku: 'FRU-0067', origen: 3, destino: 2, cantidad: 30, motivo: 'Maduración lista para góndola.', usuario: 2 },
  { id: 43, dia: 25, hora: 11, minuto: 15, sku: 'ABA-0112', origen: 1, destino: 2, cantidad: 60, motivo: 'Cubrir el faltante mientras llega la OC-2026-0015.', usuario: 2 },
  { id: 44, dia: 29, hora: 14, minuto: 50, sku: 'LAC-0102', origen: 3, destino: 2, cantidad: 20, motivo: 'Reposición de la bodega de despacho.', usuario: 2 },
]

for (const [sku, bodega, inicial] of ubicaciones) {
  intentos.push({ fecha: fechaOct(1, 7), sku, id_bodega: bodega, tipo: 'AJUSTE_POSITIVO', cantidad: inicial, costo: Math.round(productoPorSku.get(sku)!.precio_venta * 0.71), motivo: 'Inventario inicial', documento: 'Conteo físico 01/10/2026', usuario: 1 })
}

const perecedero = (sku: string) => /^(FRU|CAR)|^LAC-01|^LAC-02/.test(sku)
for (let dia = 1; dia <= 29; dia++) {
  const sabado = new Date(Date.UTC(2026, 9, dia)).getUTCDay() === 6
  for (const [sku, bodega, , venta] of ubicaciones) {
    if (venta === 0) continue
    // Cada producto se descarga del POS a una hora distinta dentro del turno (11:00–15:30 y 17:00–21:30).
    for (const [turno, desdeHora, parte] of [[1, 11, 0.45], [2, 17, 0.55]] as const) {
      const hora = desdeHora
      const minuto = Math.floor(azarHora() * 270)
      if (dia === 29 && turno === 2) continue
      const bruto = venta * parte * (0.75 + azar() * 0.5) * (sabado ? 1.3 : 1)
      const d = decimales(sku)
      const cantidad = d === 0 ? Math.floor(bruto) + (azar() < bruto % 1 ? 1 : 0) : redondear(bruto, 3)
      if (cantidad <= 0) continue
      intentos.push({ fecha: fechaOct(dia, hora, minuto), sku, id_bodega: bodega, tipo: 'SALIDA', cantidad, motivo: null, documento: `Cierre POS ${String(dia).padStart(2, '0')}/10 turno ${turno}`, usuario: JEFE[bodega] })
    }
    if ([7, 14, 21, 28].includes(dia) && perecedero(sku)) {
      const d = decimales(sku)
      const cantidad = d === 0 ? 2 + Math.floor(azar() * 4) : redondear(1.5 + azar() * 3.5, 3)
      intentos.push({ fecha: fechaOct(dia, 18), sku, id_bodega: bodega, tipo: 'AJUSTE_NEGATIVO', cantidad, motivo: dia % 14 === 0 ? 'Merma: producto vencido' : 'Merma: producto en mal estado', documento: null, usuario: JEFE[bodega] })
    }
  }
}

intentos.push(
  { fecha: fechaOct(12, 19), sku: 'BEB-0044', id_bodega: 2, tipo: 'AJUSTE_NEGATIVO', cantidad: 12, motivo: 'Daño: paca rota por el montacargas', documento: null, usuario: 2 },
  { fecha: fechaOct(23, 16, 30), sku: 'ABA-0322', id_bodega: 1, tipo: 'AJUSTE_POSITIVO', cantidad: 4, motivo: 'Diferencia de conteo físico', documento: 'Conteo cíclico pasillo 4', usuario: 3 },
  { fecha: fechaOct(24, 17, 10), sku: 'LAC-0102', id_bodega: 2, tipo: 'DEVOLUCION_CLIENTE', cantidad: 2, motivo: 'Producto con sabor alterado', documento: 'FV-POS-0018832', usuario: 2 },
  { fecha: fechaOct(26, 15, 40), sku: 'ASE-0512', id_bodega: 1, tipo: 'DEVOLUCION_CLIENTE', cantidad: 1, motivo: 'Empaque defectuoso', documento: 'FV-POS-0019107', usuario: 3 },
  { fecha: fechaOct(28, 12, 5), sku: 'CUI-0103', id_bodega: 1, tipo: 'DEVOLUCION_CLIENTE', cantidad: 1, motivo: 'El cliente recibió otra referencia', documento: 'FV-POS-0019544', usuario: 3 },
  { fecha: fechaOct(29, 15, 35), sku: 'BEB-0120', id_bodega: 2, tipo: 'DEVOLUCION_CLIENTE', cantidad: 3, motivo: 'Botellas sin gas', documento: 'FV-POS-0019781', usuario: 2 },
)

const numeroOrden = (id: number) => `OC-2026-${String(id).padStart(4, '0')}`
for (const o of defOrdenes) {
  for (const r of o.recepciones ?? []) {
    for (const [sku, cantidad] of r.items) {
      const costo = Math.round(precioCompra(o.proveedor, sku) * (0.97 + azar() * 0.06))
      intentos.push({ fecha: fechaOct(r.dia, r.hora), sku, id_bodega: o.bodega, tipo: 'ENTRADA_COMPRA', cantidad, costo, motivo: null, documento: numeroOrden(o.id), usuario: JEFE[o.bodega] })
    }
  }
  for (const dv of o.devoluciones ?? []) {
    for (const [sku, cantidad] of dv.items) {
      intentos.push({ fecha: fechaOct(dv.dia, 14), sku, id_bodega: o.bodega, tipo: 'DEVOLUCION_PROVEEDOR', cantidad, motivo: dv.motivo, documento: numeroOrden(o.id), usuario: JEFE[o.bodega] })
    }
  }
}

// ---------- Ejecución en orden cronológico ----------

type Paso = { fecha: string; correr: () => void }
const pasos: Paso[] = intentos.map((i) => ({ fecha: i.fecha, correr: () => void aplicarMovimiento(i) }))
for (const t of trasladosDef) {
  const fecha = fechaOct(t.dia, t.hora, t.minuto)
  pasos.push({
    fecha,
    correr: () => {
      const salida = aplicarMovimiento({ fecha, sku: t.sku, id_bodega: t.origen, tipo: 'TRASLADO_SALIDA', cantidad: t.cantidad, motivo: t.motivo, documento: `TR-${t.id}`, usuario: t.usuario })
      if (!salida) return
      const entrada = aplicarMovimiento({ fecha, sku: t.sku, id_bodega: t.destino, tipo: 'TRASLADO_ENTRADA', cantidad: salida.cantidad, costo: salida.costo_unitario, motivo: t.motivo, documento: `TR-${t.id}`, usuario: t.usuario })!
      traslados.push({ id_traslado: t.id, sku: t.sku, id_bodega_origen: t.origen, id_bodega_destino: t.destino, cantidad: salida.cantidad, motivo: t.motivo, id_usuario: t.usuario, fecha, movimientos: { salida: salida.id_movimiento, entrada: entrada.id_movimiento } })
    },
  })
}
pasos.sort((a, b) => (a.fecha < b.fecha ? -1 : a.fecha > b.fecha ? 1 : 0))
for (const p of pasos) p.correr()

// ---------- Órdenes resultantes ----------

export const ordenes: OrdenCompra[] = defOrdenes.map((o) => {
  let idDetalle = o.id * 10
  const items: DetalleOrden[] = o.items.map(([sku, cantidad]) => {
    const recibida = (o.recepciones ?? []).flatMap((r) => r.items).filter(([s]) => s === sku).reduce((a, [, c]) => a + c, 0)
    const devuelta = (o.devoluciones ?? []).flatMap((r) => r.items).filter(([s]) => s === sku).reduce((a, [, c]) => a + c, 0)
    return { id_detalle: ++idDetalle, sku, cantidad, precio_unitario: precioCompra(o.proveedor, sku), cantidad_recibida: recibida, cantidad_devuelta: devuelta }
  })
  const detalle = (sku: string) => items.find((x) => x.sku === sku)!.id_detalle
  const recepciones: Recepcion[] = (o.recepciones ?? []).map((r, i) => ({
    id_recepcion: o.id * 10 + i + 1,
    fecha: fechaOct(r.dia, r.hora),
    id_usuario: JEFE[o.bodega],
    observaciones: r.observaciones,
    items: r.items.map(([sku, cantidad]) => ({ id_detalle: detalle(sku), cantidad })),
  }))
  const devoluciones: DevolucionProveedor[] = (o.devoluciones ?? []).map((d, i) => ({
    id_devolucion: o.id * 10 + i + 1,
    id_orden: o.id,
    id_proveedor: o.proveedor,
    fecha: fechaOct(d.dia, 14),
    id_usuario: JEFE[o.bodega],
    motivo: d.motivo,
    items: d.items.map(([sku, cantidad]) => ({ id_detalle: detalle(sku), cantidad })),
  }))
  const pendiente = items.some((x) => x.cantidad_recibida < x.cantidad)
  let estado: EstadoOrden = 'BORRADOR'
  if (o.anulada) estado = 'ANULADA'
  else if (recepciones.length) estado = pendiente ? 'RECIBIDA_PARCIAL' : 'RECIBIDA'
  else if (o.aprobada) estado = 'APROBADA'
  const ultimo = o.anulada?.dia ?? o.recepciones?.at(-1)?.dia ?? o.aprobada ?? o.creada
  return {
    id_orden: o.id,
    numero: numeroOrden(o.id),
    id_proveedor: o.proveedor,
    id_bodega_destino: o.bodega,
    estado,
    fecha_creacion: fechaOct(o.creada, 9),
    fecha_actualizacion: fechaOct(Math.max(ultimo, o.devoluciones?.at(-1)?.dia ?? 0), 15),
    id_usuario: 4,
    total: items.reduce((a, x) => a + x.cantidad * x.precio_unitario, 0),
    motivo_anulacion: o.anulada?.motivo ?? null,
    items,
    recepciones,
    devoluciones,
  }
})

// ---------- Vistas derivadas ----------

/** Saldos actuales, como los devuelve GET /api/stock. */
export function saldosActuales(): Saldo[] {
  return [...estadoSaldos.entries()].map(([k, s]) => {
    const [sku, b] = k.split('|')
    const p = productoPorSku.get(sku)!
    return { sku, id_bodega: Number(b), cantidad: s.cantidad, costo_promedio: s.costo, valor: redondear(s.cantidad * s.costo, 2), stock_minimo: p.stock_minimo, bajo_minimo: s.cantidad <= p.stock_minimo }
  })
}

/** Saldo inicial de un producto y bodega antes de una fecha, reconstruido desde el kardex. */
export function saldoAntesDe(sku: string, id_bodega: number, fecha: string) {
  const previos = movimientos.filter((m) => m.sku === sku && m.id_bodega === id_bodega && m.fecha < fecha)
  const ultimo = previos.at(-1)
  return { cantidad: ultimo?.saldo_resultante ?? 0, valor: ultimo?.valor_resultante ?? 0 }
}

export const siguienteIdMovimiento = () => siguienteMovimiento
