// Cliente de la API pública del gateway, simulado en memoria.
// Cada función corresponde a un endpoint de la entrega 2 (ruta en el comentario) y
// devuelve la misma forma de respuesta. Para conectar el gateway real basta con
// reemplazar el cuerpo de cada función por un fetch a VITE_API_URL + la ruta.
import type {
  AgruparValorizacion, AlertaStock, Bodega, Categoria, Dashboard, ErrorApi, EstadoOrden, FilaValorizacion,
  ItemCantidad, ItemRotacion, Kardex, Movimiento, Notificacion, OrdenCompra, Paginado, Producto,
  Proveedor, ProductoSuministrado, RespuestaLogin, Rol, RolConPermisos, Saldo, StockProducto,
  TipoMovimiento, TipoMovimientoManual, Traslado, Usuario,
} from './types'
import {
  bodegaPorId, bodegas, categoriaPorId, categoriaRaiz, categorias, productoPorSku, productos, productosPorProveedor,
  proveedorPorId, proveedores, roles, usuarios,
} from './mock/maestros'
import {
  AHORA, ahoraSimulado, aplicarMovimiento, esEntrada, movimientos, notificaciones, ordenes, saldoAntesDe, saldosActuales, traslados,
} from './mock/simulacion'

export class ApiError extends Error {
  status: number
  cuerpo: ErrorApi
  constructor(status: number, codigo: string, mensaje: string, detalles?: Record<string, string[]>) {
    super(mensaje)
    this.status = status
    this.cuerpo = { error: { codigo, mensaje, detalles } }
  }
}

const esperar = <T>(valor: T, ms = 220): Promise<T> =>
  new Promise((ok) => setTimeout(() => ok(structuredClone(valor)), ms + Math.random() * 120))

const fallar = (status: number, codigo: string, mensaje: string, detalles?: Record<string, string[]>): Promise<never> =>
  new Promise((_, mal) => setTimeout(() => mal(new ApiError(status, codigo, mensaje, detalles)), 260))

function paginar<T>(filas: T[], page = 1, per_page = 20): Paginado<T> {
  const pp = Math.min(Math.max(per_page, 1), 100)
  const p = Math.max(page, 1)
  return { data: filas.slice((p - 1) * pp, p * pp), meta: { page: p, per_page: pp, total: filas.length } }
}

// Los filtros de fecha (AAAA-MM-DD) son días locales de Manizales (UTC−5), no días UTC:
// así una salida de las 9:30 p. m. no aparece en el día siguiente.
const inicioDia = (d: string) => (d.length === 10 ? `${d}T05:00:00Z` : d)
const finDia = (d: string) => {
  if (d.length !== 10) return d
  const siguiente = new Date(Date.parse(`${d}T05:00:00Z`) + 864e5)
  return siguiente.toISOString().replace(/\.\d{3}Z$/, 'Z')
}
const enRango = (fecha: string, desde?: string, hasta?: string) =>
  (!desde || fecha >= inicioDia(desde)) && (!hasta || fecha < finDia(hasta))

const recientes = <T extends { fecha: string }>(a: T, b: T) => (a.fecha < b.fecha ? 1 : -1)

// ---------- API Gateway: /api/auth, /api/usuarios, /api/roles ----------

export const auth = {
  /** POST /api/auth/login */
  login(email: string, password: string): Promise<RespuestaLogin> {
    const detalles: Record<string, string[]> = {}
    if (!email.trim()) detalles.email = ['Escribe tu correo.']
    if (!password) detalles.password = ['Escribe tu contraseña.']
    if (Object.keys(detalles).length) return fallar(422, 'VALIDACION', 'Revisa los campos marcados.', detalles)
    const u = usuarios.find((x) => x.email.toLowerCase() === email.trim().toLowerCase())
    if (!u) return fallar(401, 'CREDENCIALES_INVALIDAS', 'El correo o la contraseña no coinciden.')
    if (u.estado === 'INACTIVO') return fallar(403, 'USUARIO_INACTIVO', 'Este usuario está inactivo. Pide al administrador que lo active.')
    return esperar({ token: `demo|${u.id}|${crypto.randomUUID()}`, usuario: { id: u.id, nombre: u.nombre, email: u.email, rol: u.rol } }, 500)
  },
  /** POST /api/auth/logout → 204 */
  logout: () => esperar(undefined, 120),
  /** POST /api/auth/password/recuperar → 202 siempre */
  recuperar: (_email: string) => esperar({ aceptado: true }, 500),
  /** PUT /api/auth/password → 204 */
  cambiarPassword(actual: string, nueva: string): Promise<void> {
    if (!actual) return fallar(422, 'VALIDACION', 'Escribe tu contraseña actual.', { password_actual: ['Obligatoria.'] })
    if (nueva.length < 8) return fallar(422, 'VALIDACION', 'La contraseña nueva debe tener al menos 8 caracteres.', { password_nueva: ['Mínimo 8 caracteres.'] })
    return esperar(undefined, 400)
  },
}

export const usuariosApi = {
  /** GET /api/usuarios */
  listar: (f: { rol?: Rol; estado?: Usuario['estado']; page?: number } = {}) =>
    esperar(paginar(usuarios.filter((u) => (!f.rol || u.rol === f.rol) && (!f.estado || u.estado === f.estado)), f.page)),
  /** POST /api/usuarios/{id}/inactivar | /activar */
  cambiarEstado(id: number, estado: Usuario['estado']) {
    const u = usuarios.find((x) => x.id === id)
    if (!u) return fallar(404, 'NO_EXISTE', 'El usuario no existe.')
    u.estado = estado
    return esperar(u)
  },
}

/** GET /api/roles */
export const rolesApi = { listar: (): Promise<RolConPermisos[]> => esperar(roles) }

// ---------- ms-productos: /api/categorias, /api/productos ----------

export const categoriasApi = {
  /** GET /api/categorias → listado con subcategorías */
  listar(f: { estado?: Categoria['estado'] } = {}): Promise<Categoria[]> {
    const raiz = categorias.filter((c) => c.id_categoria_padre === null && (!f.estado || c.estado === f.estado))
    return esperar(raiz.map((c) => ({ ...c, subcategorias: categorias.filter((s) => s.id_categoria_padre === c.id_categoria) })))
  },
}

export interface FiltroProductos { q?: string; id_categoria?: number; estado?: Producto['estado']; precio_min?: number; precio_max?: number; page?: number; per_page?: number }

export const productosApi = {
  /** GET /api/productos (RF12) */
  listar(f: FiltroProductos = {}): Promise<Paginado<Producto>> {
    const q = f.q?.trim().toLowerCase()
    const filas = productos.filter((p) =>
      (!q || p.sku.toLowerCase().includes(q) || p.nombre.toLowerCase().includes(q)) &&
      (!f.id_categoria || p.id_categoria === f.id_categoria || categoriaRaiz(p.id_categoria).id_categoria === f.id_categoria) &&
      (!f.estado || p.estado === f.estado) &&
      (f.precio_min === undefined || p.precio_venta >= f.precio_min) &&
      (f.precio_max === undefined || p.precio_venta <= f.precio_max))
    return esperar(paginar(filas, f.page, f.per_page))
  },
  /** GET /api/productos/sku/{sku} */
  porSku(sku: string): Promise<Producto> {
    const p = productoPorSku.get(sku)
    return p ? esperar(p) : fallar(404, 'NO_EXISTE', `No existe un producto con SKU ${sku}.`)
  },
  /** POST /api/productos/{id}/inactivar | /activar */
  cambiarEstado(id: number, estado: Producto['estado']) {
    const p = productos.find((x) => x.id_producto === id)
    if (!p) return fallar(404, 'NO_EXISTE', 'El producto no existe.')
    p.estado = estado
    return esperar(p)
  },
}

// ---------- ms-inventario: /api/bodegas, /api/stock, /api/movimientos, /api/kardex, /api/traslados, /api/devoluciones-cliente ----------

export const bodegasApi = {
  /** GET /api/bodegas */
  listar: (f: { estado?: Bodega['estado'] } = {}): Promise<Bodega[]> => esperar(bodegas.filter((b) => !f.estado || b.estado === f.estado)),
}

export interface FiltroStock { sku?: string; id_bodega?: number; bajo_minimo?: boolean; page?: number; per_page?: number }

export const stockApi = {
  /** GET /api/stock */
  listar(f: FiltroStock = {}): Promise<Paginado<Saldo>> {
    const filas = saldosActuales()
      .filter((s) => (!f.sku || s.sku === f.sku) && (!f.id_bodega || s.id_bodega === f.id_bodega) && (!f.bajo_minimo || s.bajo_minimo))
      .sort((a, b) => a.sku.localeCompare(b.sku) || a.id_bodega - b.id_bodega)
    return esperar(paginar(filas, f.page, f.per_page ?? 100))
  },
  /** GET /api/stock/{sku} (RF05) */
  porSku(sku: string): Promise<StockProducto> {
    const filas = saldosActuales().filter((s) => s.sku === sku)
    if (!productoPorSku.has(sku)) return fallar(404, 'NO_EXISTE', `No existe un producto con SKU ${sku}.`)
    return esperar({
      sku,
      por_bodega: filas.map(({ id_bodega, cantidad, costo_promedio, valor }) => ({ id_bodega, cantidad, costo_promedio, valor })),
      total: { cantidad: filas.reduce((a, s) => a + s.cantidad, 0), valor: filas.reduce((a, s) => a + s.valor, 0) },
    })
  },
}

export interface FiltroMovimientos { sku?: string; id_bodega?: number; tipo?: TipoMovimiento; desde?: string; hasta?: string; page?: number; per_page?: number }

export interface NuevoMovimiento { sku: string; id_bodega: number; tipo: TipoMovimientoManual; cantidad: number; costo_unitario?: number; motivo: string; documento_referencia?: string }

function validarSalida(sku: string, id_bodega: number, cantidad: number): Promise<never> | null {
  const saldo = saldosActuales().find((s) => s.sku === sku && s.id_bodega === id_bodega)?.cantidad ?? 0
  if (cantidad > saldo) return fallar(409, 'STOCK_INSUFICIENTE', `No hay saldo suficiente: quedan ${saldo} y la salida pide ${cantidad}.`, { cantidad: [`Máximo ${saldo}.`] })
  return null
}

export const movimientosApi = {
  /** GET /api/movimientos */
  listar(f: FiltroMovimientos = {}): Promise<Paginado<Movimiento>> {
    const filas = movimientos
      .filter((m) => (!f.sku || m.sku === f.sku) && (!f.id_bodega || m.id_bodega === f.id_bodega) && (!f.tipo || m.tipo === f.tipo) && enRango(m.fecha, f.desde, f.hasta))
      .sort(recientes)
    return esperar(paginar(filas, f.page, f.per_page))
  },
  /** POST /api/movimientos → 201; publica MovimientoRegistrado y, si corresponde, StockBajoUmbral */
  crear(m: NuevoMovimiento, id_usuario: number): Promise<Movimiento> {
    const detalles: Record<string, string[]> = {}
    if (!m.sku) detalles.sku = [m.tipo === 'SALIDA' ? 'Elige el producto que sale.' : 'Elige el producto que se ajusta.']
    if (!(m.cantidad > 0)) detalles.cantidad = ['La cantidad debe ser mayor que cero.']
    if (m.tipo !== 'SALIDA' && !m.motivo.trim()) detalles.motivo = ['Todo ajuste exige un motivo.']
    if (m.tipo === 'SALIDA' && !m.documento_referencia?.trim()) detalles.documento_referencia = ['Indica el documento del POS que respalda la salida.']
    if (Object.keys(detalles).length) return fallar(422, 'VALIDACION', 'Revisa los campos marcados.', detalles)
    const p = productoPorSku.get(m.sku)
    if (!p) return fallar(404, 'PRODUCTO_INEXISTENTE', `No existe un producto con SKU ${m.sku}.`)
    if (!esEntrada(m.tipo)) { const e = validarSalida(m.sku, m.id_bodega, m.cantidad); if (e) return e }
    const mov = aplicarMovimiento({ fecha: ahoraSimulado(), sku: m.sku, id_bodega: m.id_bodega, tipo: m.tipo, cantidad: m.cantidad, costo: m.costo_unitario, motivo: m.motivo || null, documento: m.documento_referencia || null, usuario: id_usuario })!
    return esperar(mov, 450)
  },
}

export const kardexApi = {
  /** GET /api/kardex?sku&id_bodega&desde&hasta (obligatorios) */
  consultar(f: { sku: string; id_bodega: number; desde: string; hasta: string }): Promise<Kardex> {
    if (!f.sku || !f.id_bodega || !f.desde || !f.hasta) return fallar(422, 'VALIDACION', 'El kardex necesita producto, bodega y rango de fechas.')
    const lista = movimientos.filter((m) => m.sku === f.sku && m.id_bodega === f.id_bodega && enRango(m.fecha, f.desde, f.hasta))
    const ultimo = lista.at(-1)
    const inicial = saldoAntesDe(f.sku, f.id_bodega, inicioDia(f.desde))
    return esperar({ ...f, saldo_inicial: inicial, movimientos: lista, saldo_final: ultimo ? { cantidad: ultimo.saldo_resultante, valor: ultimo.valor_resultante } : inicial })
  },
}

export const trasladosApi = {
  /** GET /api/traslados */
  listar: (f: { sku?: string; desde?: string; hasta?: string; page?: number } = {}): Promise<Paginado<Traslado>> =>
    esperar(paginar(traslados.filter((t) => (!f.sku || t.sku === f.sku) && enRango(t.fecha, f.desde, f.hasta)).sort(recientes), f.page)),
  /** POST /api/traslados → 201 con sus dos movimientos */
  crear(t: { sku: string; id_bodega_origen: number; id_bodega_destino: number; cantidad: number; motivo?: string }, id_usuario: number): Promise<Traslado> {
    const detalles: Record<string, string[]> = {}
    if (!t.sku) detalles.sku = ['Elige el producto que se traslada.']
    if (!(t.cantidad > 0)) detalles.cantidad = ['La cantidad debe ser mayor que cero.']
    if (t.id_bodega_origen === t.id_bodega_destino) detalles.id_bodega_destino = ['Elige una bodega distinta a la de origen.']
    if (Object.keys(detalles).length) return fallar(422, 'VALIDACION', 'Revisa los campos marcados.', detalles)
    const e = validarSalida(t.sku, t.id_bodega_origen, t.cantidad)
    if (e) return e
    const fecha = ahoraSimulado()
    const id = Math.max(...traslados.map((x) => x.id_traslado)) + 1
    const salida = aplicarMovimiento({ fecha, sku: t.sku, id_bodega: t.id_bodega_origen, tipo: 'TRASLADO_SALIDA', cantidad: t.cantidad, motivo: t.motivo ?? null, documento: `TR-${id}`, usuario: id_usuario })!
    const entrada = aplicarMovimiento({ fecha, sku: t.sku, id_bodega: t.id_bodega_destino, tipo: 'TRASLADO_ENTRADA', cantidad: salida.cantidad, costo: salida.costo_unitario, motivo: t.motivo ?? null, documento: `TR-${id}`, usuario: id_usuario })!
    const nuevo: Traslado = { id_traslado: id, ...t, motivo: t.motivo ?? null, id_usuario, fecha, movimientos: { salida: salida.id_movimiento, entrada: entrada.id_movimiento } }
    traslados.push(nuevo)
    return esperar(nuevo, 450)
  },
}

export const devolucionesClienteApi = {
  /** GET /api/devoluciones-cliente */
  listar: (f: { sku?: string; page?: number } = {}): Promise<Paginado<Movimiento>> =>
    esperar(paginar(movimientos.filter((m) => m.tipo === 'DEVOLUCION_CLIENTE' && (!f.sku || m.sku === f.sku)).sort(recientes), f.page)),
  /** POST /api/devoluciones-cliente → 201 movimiento DEVOLUCION_CLIENTE (RF13) */
  crear(d: { sku: string; id_bodega: number; cantidad: number; factura_pos: string; motivo: string }, id_usuario: number): Promise<Movimiento> {
    const detalles: Record<string, string[]> = {}
    if (!d.sku) detalles.sku = ['Elige el producto que devuelve el cliente.']
    if (!d.factura_pos.trim()) detalles.factura_pos = ['Indica la factura del POS.']
    if (!d.motivo.trim()) detalles.motivo = ['Indica el motivo de la devolución.']
    if (!(d.cantidad > 0)) detalles.cantidad = ['La cantidad debe ser mayor que cero.']
    if (Object.keys(detalles).length) return fallar(422, 'VALIDACION', 'Revisa los campos marcados.', detalles)
    const mov = aplicarMovimiento({ fecha: ahoraSimulado(), sku: d.sku, id_bodega: d.id_bodega, tipo: 'DEVOLUCION_CLIENTE', cantidad: d.cantidad, motivo: d.motivo, documento: d.factura_pos, usuario: id_usuario })!
    return esperar(mov, 450)
  },
}

// ---------- ms-proveedores: /api/proveedores ----------

export const proveedoresApi = {
  /** GET /api/proveedores */
  listar(f: { q?: string; estado?: Proveedor['estado']; sku?: string; page?: number } = {}): Promise<Paginado<Proveedor>> {
    const q = f.q?.trim().toLowerCase()
    const filas = proveedores.filter((p) =>
      (!q || p.nit.includes(q) || p.razon_social.toLowerCase().includes(q)) && (!f.estado || p.estado === f.estado) &&
      (!f.sku || productosPorProveedor[p.id_proveedor]?.some((x) => x.sku === f.sku)))
    return esperar(paginar(filas, f.page))
  },
  /** GET /api/proveedores/{id} */
  obtener(id: number): Promise<Proveedor> {
    const p = proveedores.find((x) => x.id_proveedor === id)
    return p ? esperar(p) : fallar(404, 'NO_EXISTE', 'El proveedor no existe.')
  },
  /** GET /api/proveedores/{id}/productos */
  productos: (id: number): Promise<ProductoSuministrado[]> => esperar(productosPorProveedor[id] ?? []),
}

// ---------- ms-compras: /api/ordenes-compra, /api/devoluciones-proveedor ----------

const PENDIENTES: EstadoOrden[] = ['BORRADOR', 'APROBADA', 'RECIBIDA_PARCIAL']

export const ordenesApi = {
  /** GET /api/ordenes-compra */
  listar(f: { estado?: EstadoOrden; id_proveedor?: number; page?: number } = {}): Promise<Paginado<OrdenCompra>> {
    const filas = ordenes.filter((o) => (!f.estado || o.estado === f.estado) && (!f.id_proveedor || o.id_proveedor === f.id_proveedor))
      .sort((a, b) => b.id_orden - a.id_orden)
    return esperar(paginar(filas, f.page))
  },
  /** GET /api/ordenes-compra/{id} */
  obtener(id: number): Promise<OrdenCompra> {
    const o = ordenes.find((x) => x.id_orden === id)
    return o ? esperar(o) : fallar(404, 'NO_EXISTE', 'La orden de compra no existe.')
  },
  /** POST /api/ordenes-compra/{id}/aprobar */
  aprobar(id: number): Promise<OrdenCompra> {
    const o = ordenes.find((x) => x.id_orden === id)
    if (!o) return fallar(404, 'NO_EXISTE', 'La orden de compra no existe.')
    if (o.estado !== 'BORRADOR') return fallar(409, 'TRANSICION_INVALIDA', `Solo se aprueban órdenes en borrador; esta está ${o.estado}.`)
    o.estado = 'APROBADA'
    o.fecha_actualizacion = ahoraSimulado()
    return esperar(o, 400)
  },
  /** POST /api/ordenes-compra/{id}/anular */
  anular(id: number, motivo: string): Promise<OrdenCompra> {
    const o = ordenes.find((x) => x.id_orden === id)
    if (!o) return fallar(404, 'NO_EXISTE', 'La orden de compra no existe.')
    if (!motivo.trim()) return fallar(422, 'VALIDACION', 'Indica el motivo de la anulación.', { motivo: ['Obligatorio.'] })
    if (o.recepciones.length) return fallar(409, 'TRANSICION_INVALIDA', 'La orden ya tiene recepciones y no se puede anular.')
    o.estado = 'ANULADA'
    o.motivo_anulacion = motivo
    return esperar(o, 400)
  },
  /** POST /api/ordenes-compra/{id}/recepciones → publica MercanciaRecibida */
  recibir(id: number, items: ItemCantidad[], observaciones: string, id_usuario: number): Promise<OrdenCompra> {
    const o = ordenes.find((x) => x.id_orden === id)
    if (!o) return fallar(404, 'NO_EXISTE', 'La orden de compra no existe.')
    if (!['APROBADA', 'RECIBIDA_PARCIAL'].includes(o.estado)) return fallar(409, 'ORDEN_NO_APROBADA', 'Solo se recibe mercancía de órdenes aprobadas.')
    const validos = items.filter((i) => i.cantidad > 0)
    if (!validos.length) return fallar(422, 'VALIDACION', 'Indica al menos una cantidad recibida.')
    for (const i of validos) {
      const d = o.items.find((x) => x.id_detalle === i.id_detalle)!
      if (i.cantidad > d.cantidad - d.cantidad_recibida) return fallar(409, 'CANTIDAD_MAYOR_QUE_PENDIENTE', `${productoPorSku.get(d.sku)!.nombre}: quedan ${d.cantidad - d.cantidad_recibida} por recibir.`)
    }
    const fecha = ahoraSimulado()
    for (const i of validos) {
      const d = o.items.find((x) => x.id_detalle === i.id_detalle)!
      d.cantidad_recibida += i.cantidad
      aplicarMovimiento({ fecha, sku: d.sku, id_bodega: o.id_bodega_destino, tipo: 'ENTRADA_COMPRA', cantidad: i.cantidad, costo: d.precio_unitario, motivo: null, documento: o.numero, usuario: id_usuario })
    }
    o.recepciones.push({ id_recepcion: o.id_orden * 10 + o.recepciones.length + 1, fecha, id_usuario, observaciones, items: validos })
    o.estado = o.items.every((d) => d.cantidad_recibida >= d.cantidad) ? 'RECIBIDA' : 'RECIBIDA_PARCIAL'
    o.fecha_actualizacion = fecha
    return esperar(o, 500)
  },
  /** POST /api/ordenes-compra → 201 orden en BORRADOR; publica OrdenCompraActualizada */
  crear(o: { id_proveedor: number; id_bodega_destino: number; items: Array<{ sku: string; cantidad: number; precio_unitario: number }> }, id_usuario: number): Promise<OrdenCompra> {
    const prov = proveedores.find((p) => p.id_proveedor === o.id_proveedor)
    if (!prov || prov.estado !== 'ACTIVO') return fallar(422, 'PROVEEDOR_INVALIDO', 'El proveedor no existe o está inactivo.', { id_proveedor: ['Elige un proveedor activo.'] })
    const items = o.items.filter((i) => i.sku && i.cantidad > 0)
    if (!items.length) return fallar(422, 'SIN_ITEMS', 'La orden necesita al menos un producto con cantidad.', { items: ['Agrega al menos un producto.'] })
    const id = Math.max(...ordenes.map((x) => x.id_orden)) + 1
    const fecha = ahoraSimulado()
    const nueva: OrdenCompra = {
      id_orden: id, numero: `OC-2026-${String(id).padStart(4, '0')}`, id_proveedor: o.id_proveedor, id_bodega_destino: o.id_bodega_destino,
      estado: 'BORRADOR', fecha_creacion: fecha, fecha_actualizacion: fecha, id_usuario, motivo_anulacion: null,
      total: items.reduce((a, i) => a + i.cantidad * i.precio_unitario, 0),
      items: items.map((i, n) => ({ id_detalle: id * 10 + n + 1, ...i, cantidad_recibida: 0, cantidad_devuelta: 0 })),
      recepciones: [], devoluciones: [],
    }
    ordenes.push(nueva)
    return esperar(nueva, 500)
  },
  /** POST /api/ordenes-compra/{id}/devoluciones → publica DevolucionProveedorRegistrada (RF13) */
  devolver(id: number, items: ItemCantidad[], motivo: string, id_usuario: number): Promise<OrdenCompra> {
    const o = ordenes.find((x) => x.id_orden === id)
    if (!o) return fallar(404, 'NO_EXISTE', 'La orden de compra no existe.')
    if (!motivo.trim()) return fallar(422, 'VALIDACION', 'Indica el motivo de la devolución.', { motivo: ['Obligatorio.'] })
    const validos = items.filter((i) => i.cantidad > 0)
    if (!validos.length) return fallar(422, 'VALIDACION', 'Indica al menos una cantidad a devolver.')
    for (const i of validos) {
      const d = o.items.find((x) => x.id_detalle === i.id_detalle)!
      if (i.cantidad > d.cantidad_recibida - d.cantidad_devuelta) return fallar(409, 'CANTIDAD_MAYOR_QUE_RECIBIDA', `${productoPorSku.get(d.sku)!.nombre}: solo se pueden devolver ${d.cantidad_recibida - d.cantidad_devuelta}.`)
    }
    const fecha = ahoraSimulado()
    for (const i of validos) {
      const d = o.items.find((x) => x.id_detalle === i.id_detalle)!
      d.cantidad_devuelta += i.cantidad
      aplicarMovimiento({ fecha, sku: d.sku, id_bodega: o.id_bodega_destino, tipo: 'DEVOLUCION_PROVEEDOR', cantidad: i.cantidad, motivo, documento: o.numero, usuario: id_usuario })
    }
    o.devoluciones.push({ id_devolucion: o.id_orden * 10 + o.devoluciones.length + 1, id_orden: o.id_orden, id_proveedor: o.id_proveedor, fecha, id_usuario, motivo, items: validos })
    return esperar(o, 500)
  },
  pendientes: () => ordenes.filter((o) => PENDIENTES.includes(o.estado)).length,
}

/** Búsqueda global de la barra: SKU o nombre de producto, número de orden y número o documento de movimiento. */
export function buscarTodo(q: string) {
  const t = q.trim().toLowerCase()
  const numeroMov = /^mov-?0*(\d+)$/i.exec(q.trim())?.[1]
  return esperar({
    productos: productos.filter((p) => p.sku.toLowerCase().includes(t) || p.nombre.toLowerCase().includes(t)).slice(0, 12),
    ordenes: ordenes.filter((o) => o.numero.toLowerCase().includes(t)).slice(0, 12),
    movimientos: movimientos.filter((m) => (numeroMov && m.id_movimiento === Number(numeroMov)) || m.documento_referencia?.toLowerCase().includes(t)).slice(-12).reverse(),
    proveedores: proveedores.filter((p) => p.razon_social.toLowerCase().includes(t) || p.nit.includes(t)).slice(0, 8),
  })
}

export const devolucionesProveedorApi = {
  /** GET /api/devoluciones-proveedor */
  listar: () => esperar(paginar(ordenes.flatMap((o) => o.devoluciones).sort(recientes))),
}

// ---------- ms-reportes: /api/dashboard, /api/reportes/* ----------

/** Rotación = unidades que salieron en el periodo / saldo promedio al cierre de cada día. */
function rotacionPorSku(desde: string, hasta: string, id_bodega?: number): ItemRotacion[] {
  const cortes: string[] = []
  for (let t = Date.parse(desde.slice(0, 10) + 'T05:00:00Z') + 864e5; t <= Date.parse(hasta) + 864e5; t += 864e5) cortes.push(new Date(Math.min(t, Date.parse(hasta))).toISOString())
  return productos.filter((p) => p.estado === 'ACTIVO').map((p) => {
    const lista = movimientos.filter((m) => m.sku === p.sku && (!id_bodega || m.id_bodega === id_bodega))
    const salidas = lista.filter((m) => m.tipo === 'SALIDA' && enRango(m.fecha, desde, hasta)).reduce((a, m) => a + m.cantidad, 0)
    const bodegasSku = [...new Set(lista.map((m) => m.id_bodega))]
    const diarios = cortes.map((c) => bodegasSku.reduce((a, b) => a + saldoAntesDe(p.sku, b, c).cantidad, 0))
    const promedio = diarios.reduce((a, x) => a + x, 0) / (diarios.length || 1) || 1
    return { sku: p.sku, nombre: p.nombre, unidades_salida: Math.round(salidas * 1000) / 1000, rotacion: Math.round((salidas / promedio) * 100) / 100 }
  }).filter((r) => r.unidades_salida > 0)
}

export const reportesApi = {
  /** GET /api/dashboard (RF14) */
  dashboard(id_bodega?: number): Promise<Dashboard> {
    const saldos = saldosActuales().filter((s) => !id_bodega || s.id_bodega === id_bodega)
    const rot = rotacionPorSku('2026-10-01', AHORA, id_bodega).sort((a, b) => b.rotacion - a.rotacion)
    return esperar({
      valor_total_inventario: Math.round(saldos.reduce((a, s) => a + s.valor, 0)),
      productos_stock_bajo: saldos.filter((s) => s.bajo_minimo).length,
      ordenes_pendientes: ordenes.filter((o) => PENDIENTES.includes(o.estado) && (!id_bodega || o.id_bodega_destino === id_bodega)).length,
      mayor_rotacion: rot.slice(0, 5),
      menor_rotacion: rot.slice(-5).reverse(),
    })
  },
  /** GET /api/reportes/valorizacion?agrupar=producto|categoria|bodega */
  valorizacion(agrupar: AgruparValorizacion, id_bodega?: number): Promise<FilaValorizacion[]> {
    const grupos = new Map<string, FilaValorizacion>()
    for (const s of saldosActuales().filter((x) => !id_bodega || x.id_bodega === id_bodega)) {
      const p = productoPorSku.get(s.sku)!
      const [k, nombre] = agrupar === 'producto' ? [p.sku, p.nombre] : agrupar === 'categoria' ? [String(categoriaRaiz(p.id_categoria).id_categoria), categoriaRaiz(p.id_categoria).nombre] : [String(s.id_bodega), bodegas.find((b) => b.id_bodega === s.id_bodega)!.nombre]
      const g = grupos.get(k) ?? { clave: k, nombre, cantidad: 0, valor: 0 }
      g.cantidad += s.cantidad
      g.valor += s.valor
      grupos.set(k, g)
    }
    return esperar([...grupos.values()].sort((a, b) => b.valor - a.valor))
  },
  /** GET /api/reportes/rotacion?desde&hasta&id_bodega&top */
  rotacion(f: { desde: string; hasta: string; id_bodega?: number; top?: number }) {
    const r = rotacionPorSku(f.desde, f.hasta, f.id_bodega).sort((a, b) => b.rotacion - a.rotacion)
    const top = f.top ?? 10
    return esperar({ mayor_rotacion: r.slice(0, top), menor_rotacion: r.slice(-top).reverse() })
  },
  /** GET /api/reportes/stock-bajo?id_bodega */
  stockBajo(id_bodega?: number): Promise<AlertaStock[]> {
    const alertas = saldosActuales().filter((s) => s.bajo_minimo && (!id_bodega || s.id_bodega === id_bodega)).map((s) => {
      const cruce = movimientos.filter((m) => m.sku === s.sku && m.id_bodega === s.id_bodega && m.saldo_resultante <= s.stock_minimo).find((m, i, arr) => i === 0 || arr[i - 1].id_movimiento !== m.id_movimiento - 1)
      return { sku: s.sku, id_bodega: s.id_bodega, saldo: s.cantidad, stock_minimo: s.stock_minimo, fecha: cruce?.fecha ?? AHORA }
    })
    return esperar(alertas.sort((a, b) => a.saldo / a.stock_minimo - b.saldo / b.stock_minimo))
  },
  /**
   * Propuesta, no está en los contratos de la entrega 2: serie diaria del valor del
   * inventario para mostrar la historia del indicador. ms-reportes la puede calcular
   * con MovimientoRegistrado (valor_resultante) agrupando por día en hora local.
   */
  serieValor(id_bodega?: number): Promise<Array<{ dia: string; valor: number }>> {
    const ultimoPorClave = new Map<string, number>()
    const serie: Array<{ dia: string; valor: number }> = []
    const lista = movimientos.filter((m) => !id_bodega || m.id_bodega === id_bodega)
    let j = 0
    for (let dia = 1; dia <= 29; dia++) {
      const corte = new Date(Date.UTC(2026, 9, dia + 1, 5)).toISOString()
      while (j < lista.length && lista[j].fecha < corte) { ultimoPorClave.set(`${lista[j].sku}|${lista[j].id_bodega}`, lista[j].valor_resultante); j++ }
      serie.push({ dia: `2026-10-${String(dia).padStart(2, '0')}`, valor: Math.round([...ultimoPorClave.values()].reduce((a, v) => a + v, 0)) })
    }
    return esperar(serie)
  },
}

// ---------- ms-notificaciones: /api/notificaciones ----------

export const notificacionesApi = {
  /** GET /api/notificaciones?leida (filtra por el rol del usuario) */
  listar: (rol: Rol, f: { leida?: boolean } = {}): Promise<Paginado<Notificacion>> =>
    esperar(paginar(notificaciones.filter((n) => (rol === 'ADMINISTRADOR' ? n.rol_destino === 'JEFE_BODEGA' : n.rol_destino === rol) && (f.leida === undefined || n.leida === f.leida)).sort(recientes), 1, 50)),
  /** POST /api/notificaciones/{id}/leida */
  marcarLeida(id: string) {
    const n = notificaciones.find((x) => x.id === id)
    if (!n) return fallar(404, 'NO_EXISTE', 'La notificación no existe.')
    n.leida = true
    return esperar(n, 120)
  },
}

// ---------- Altas de maestros (POST de cada servicio) ----------

const obligatorios = (o: Record<string, unknown>, campos: string[]) => {
  const d: Record<string, string[]> = {}
  for (const c of campos) if (o[c] === undefined || o[c] === null || String(o[c]).trim() === '' || (typeof o[c] === 'number' && Number.isNaN(o[c]))) d[c] = ['Este dato es obligatorio.']
  return d
}

export const altasApi = {
  /** POST /api/usuarios → 201 (gateway) */
  usuario(u: { nombre: string; email: string; password: string; id_rol: number }): Promise<Usuario> {
    const d = obligatorios(u, ['nombre', 'email', 'password', 'id_rol'])
    if (u.password && u.password.length < 8) d.password = ['Mínimo 8 caracteres.']
    if (u.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(u.email)) d.email = ['Escribe un correo válido.']
    if (Object.keys(d).length) return fallar(422, 'VALIDACION', 'Revisa los campos marcados.', d)
    if (usuarios.some((x) => x.email.toLowerCase() === u.email.toLowerCase())) return fallar(409, 'EMAIL_DUPLICADO', 'Ya existe un usuario con ese correo.', { email: ['Ese correo ya está registrado.'] })
    const nuevo: Usuario = { id: Math.max(...usuarios.map((x) => x.id)) + 1, nombre: u.nombre, email: u.email, rol: roles.find((r) => r.id_rol === u.id_rol)!.nombre, estado: 'ACTIVO', ultimo_acceso: null }
    usuarios.push(nuevo)
    return esperar(nuevo, 400)
  },
  /** POST /api/productos → 201 (ms-productos) */
  producto(p: Omit<Producto, 'id_producto' | 'estado'>): Promise<Producto> {
    const d = obligatorios(p, ['sku', 'nombre', 'marca', 'id_categoria', 'unidad_medida', 'precio_venta', 'stock_minimo'])
    if (p.precio_venta < 0) d.precio_venta = ['No puede ser negativo.']
    if (Object.keys(d).length) return fallar(422, 'VALIDACION', 'Revisa los campos marcados.', d)
    if (productoPorSku.has(p.sku.toUpperCase())) return fallar(409, 'SKU_DUPLICADO', `Ya existe un producto con SKU ${p.sku}.`, { sku: ['Ese SKU ya existe.'] })
    const nuevo: Producto = { ...p, sku: p.sku.toUpperCase(), id_producto: Math.max(...productos.map((x) => x.id_producto)) + 1, estado: 'ACTIVO' }
    productos.push(nuevo)
    productoPorSku.set(nuevo.sku, nuevo)
    return esperar(nuevo, 400)
  },
  /** POST /api/categorias → 201 (ms-productos) */
  categoria(c: { nombre: string; descripcion: string; id_categoria_padre: number | null }): Promise<Categoria> {
    const d = obligatorios(c, ['nombre'])
    if (Object.keys(d).length) return fallar(422, 'VALIDACION', 'Revisa los campos marcados.', d)
    if (categorias.some((x) => x.id_categoria_padre === c.id_categoria_padre && x.nombre.toLowerCase() === c.nombre.trim().toLowerCase())) return fallar(409, 'NOMBRE_REPETIDO', 'Ya existe una categoría con ese nombre en el mismo nivel.', { nombre: ['Nombre repetido en este nivel.'] })
    const nueva: Categoria = { id_categoria: Math.max(...categorias.map((x) => x.id_categoria)) + 1, nombre: c.nombre.trim(), descripcion: c.descripcion, id_categoria_padre: c.id_categoria_padre, estado: 'ACTIVO' }
    categorias.push(nueva)
    categoriaPorId.set(nueva.id_categoria, nueva)
    return esperar(nueva, 400)
  },
  /** POST /api/proveedores → 201 (ms-proveedores) */
  proveedor(p: { nit: string; razon_social: string; telefono: string; email: string; direccion: string }): Promise<Proveedor> {
    const d = obligatorios(p, ['nit', 'razon_social', 'telefono', 'email', 'direccion'])
    if (Object.keys(d).length) return fallar(422, 'VALIDACION', 'Revisa los campos marcados.', d)
    if (proveedores.some((x) => x.nit === p.nit.trim())) return fallar(409, 'NIT_DUPLICADO', 'Ya existe un proveedor con ese NIT.', { nit: ['Ese NIT ya está registrado.'] })
    const nuevo: Proveedor = { ...p, nit: p.nit.trim(), id_proveedor: Math.max(...proveedores.map((x) => x.id_proveedor)) + 1, estado: 'ACTIVO', contactos: [] }
    proveedores.push(nuevo)
    proveedorPorId.set(nuevo.id_proveedor, nuevo)
    productosPorProveedor[nuevo.id_proveedor] = []
    return esperar(nuevo, 400)
  },
  /** POST /api/bodegas → 201 (ms-inventario) */
  bodega(b: { codigo: string; nombre: string; direccion: string }): Promise<Bodega> {
    const d = obligatorios(b, ['codigo', 'nombre', 'direccion'])
    if (Object.keys(d).length) return fallar(422, 'VALIDACION', 'Revisa los campos marcados.', d)
    if (bodegas.some((x) => x.codigo.toLowerCase() === b.codigo.trim().toLowerCase())) return fallar(409, 'CODIGO_DUPLICADO', 'Ya existe una bodega con ese código.', { codigo: ['Ese código ya existe.'] })
    const nueva: Bodega = { ...b, codigo: b.codigo.trim().toUpperCase(), id_bodega: Math.max(...bodegas.map((x) => x.id_bodega)) + 1, estado: 'ACTIVO' }
    bodegas.push(nueva)
    bodegaPorId.set(nueva.id_bodega, nueva)
    return esperar(nueva, 400)
  },
}

export { AHORA }
