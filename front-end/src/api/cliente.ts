// Cliente de la API pública del gateway (/api). Cada función es un endpoint de la
// entrega 2 (ruta en el comentario). El gateway agrega X-User-Id, X-User-Role y
// X-Correlation-Id al reenviar, así que aquí nunca se envía el usuario a mano.
// Las formas que un servicio devuelve distinto del contrato se traducen aquí.
import type {
  AgruparValorizacion, AlertaStock, Bodega, Categoria, Contacto, Dashboard, DetalleOrden, DevolucionProveedor, Estado,
  EstadoOrden, FilaValorizacion, ItemCantidad, ItemMovido, ItemRotacion, Kardex, Movimiento, Notificacion,
  OrdenCompra, Paginado, Producto, ProductoSuministrado, Proveedor, Recepcion, RespuestaLogin, Rol,
  RolConPermisos, Saldo, StockProducto, TipoMovimiento, TipoMovimientoManual, Traslado, UnidadMedida, Usuario,
} from './types'
import { ApiError, pedir, todas } from './http'
import { puedeVer } from '../auth/permisos'

export { ApiError }

// ---------- Roles del gateway ----------

const ROL_POR_CODIGO: Record<string, Rol> = {
  admin: 'ADMINISTRADOR',
  jefe_bodega: 'JEFE_BODEGA',
  compras: 'COMPRAS',
  gerente: 'GERENTE',
}

export const codigoDeRol: Record<Rol, string> = {
  ADMINISTRADOR: 'admin',
  JEFE_BODEGA: 'jefe_bodega',
  COMPRAS: 'compras',
  GERENTE: 'gerente',
}

/** Un código desconocido se trata como gerente (solo consulta); el gateway igual decide. */
export const rolDeCodigo = (codigo?: string | null): Rol => ROL_POR_CODIGO[(codigo ?? '').trim().toLowerCase()] ?? 'GERENTE'

interface UsuarioGateway {
  id: number
  nombre: string
  email: string
  estado: Estado
  rol: { codigo: string; nombre: string } | null
}

const aUsuario = (u: UsuarioGateway): Usuario => ({ id: u.id, nombre: u.nombre, email: u.email, estado: u.estado, rol: rolDeCodigo(u.rol?.codigo) })

// ---------- API Gateway: /api/auth, /api/usuarios, /api/roles ----------

export const auth = {
  /** POST /api/auth/login → token personal de Sanctum */
  async login(email: string, password: string): Promise<RespuestaLogin> {
    const r = await pedir<{ token: string; usuario: UsuarioGateway }>('POST', '/auth/login', { cuerpo: { email: email.trim(), password }, sinSesion: true })
    const { id, nombre, email: correo, rol } = aUsuario(r.usuario)
    return { token: r.token, usuario: { id, nombre, email: correo, rol } }
  },
  /** POST /api/auth/logout → 204; revoca solo el token de esta sesión */
  logout: () => pedir<void>('POST', '/auth/logout'),
  /** PUT /api/auth/password → 204; revoca los demás tokens del usuario */
  cambiarPassword: (actual: string, nueva: string) =>
    pedir<void>('PUT', '/auth/password', { cuerpo: { password_actual: actual, password_nueva: nueva } }),
}

export const usuariosApi = {
  /** GET /api/usuarios */
  async listar(f: { rol?: Rol; estado?: Estado; page?: number } = {}): Promise<Paginado<Usuario>> {
    const r = await pedir<Paginado<UsuarioGateway>>('GET', '/usuarios', {
      query: { rol: f.rol && codigoDeRol[f.rol], estado: f.estado, page: f.page, per_page: 100 },
    })
    return { data: r.data.map(aUsuario), meta: r.meta }
  },
  /** Todos los usuarios, para mostrar quién registró cada documento. */
  todos: async (): Promise<Usuario[]> => (await todas<UsuarioGateway>('/usuarios')).map(aUsuario),
  /** POST /api/usuarios/{id}/inactivar | /activar */
  async cambiarEstado(id: number, estado: Estado): Promise<Usuario> {
    return aUsuario(await pedir<UsuarioGateway>('POST', `/usuarios/${id}/${estado === 'ACTIVO' ? 'activar' : 'inactivar'}`))
  },
}

/** GET /api/roles */
export const rolesApi = {
  async listar(): Promise<RolConPermisos[]> {
    const r = await pedir<Array<{ id_rol: number; codigo: string; nombre: string; permisos: string[] }>>('GET', '/roles')
    return r.map((x) => ({ ...x, rol: rolDeCodigo(x.codigo) }))
  },
}

// ---------- ms-productos: /api/categorias, /api/productos ----------

export const categoriasApi = {
  /** GET /api/categorias → raíces con sus subcategorías, todas las páginas */
  listar: (f: { estado?: Estado } = {}): Promise<Categoria[]> => todas<Categoria>('/categorias', { estado: f.estado }),
}

export interface FiltroProductos {
  q?: string
  id_categoria?: number
  estado?: Estado
  precio_min?: number
  precio_max?: number
  page?: number
  per_page?: number
}

export const productosApi = {
  /** GET /api/productos (RF12) */
  listar: (f: FiltroProductos = {}) => pedir<Paginado<Producto>>('GET', '/productos', { query: { ...f } }),
  /** Todo el catálogo, activos e inactivos. */
  todos: () => todas<Producto>('/productos'),
  /** GET /api/productos/sku/{sku} */
  porSku: (sku: string) => pedir<Producto>('GET', `/productos/sku/${encodeURIComponent(sku)}`),
  /** POST /api/productos/{id}/inactivar | /activar */
  cambiarEstado: (id: number, estado: Estado) =>
    pedir<Producto>('POST', `/productos/${id}/${estado === 'ACTIVO' ? 'activar' : 'inactivar'}`),
}

// ---------- ms-inventario ----------

export const bodegasApi = {
  /** GET /api/bodegas, todas las páginas */
  listar: (f: { estado?: Estado } = {}): Promise<Bodega[]> => todas<Bodega>('/bodegas', { estado: f.estado }),
}

export interface FiltroStock { sku?: string; id_bodega?: number; bajo_minimo?: boolean; page?: number; per_page?: number }

export const stockApi = {
  /** GET /api/stock */
  listar: (f: FiltroStock = {}) => pedir<Paginado<Saldo>>('GET', '/stock', { query: { ...f } }),
  /** Todos los saldos que cumplen el filtro (el rack necesita la bodega completa). */
  todos: (f: Omit<FiltroStock, 'page' | 'per_page'> = {}) => todas<Saldo>('/stock', { ...f }),
  /** GET /api/stock/{sku} (RF05). Un producto sin saldos responde 404: se muestra en cero. */
  async porSku(sku: string): Promise<StockProducto> {
    try {
      return await pedir<StockProducto>('GET', `/stock/${encodeURIComponent(sku)}`)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return { sku, por_bodega: [], total: { cantidad: 0, valor: 0 } }
      throw e
    }
  },
}

export interface FiltroMovimientos {
  sku?: string
  id_bodega?: number
  tipo?: TipoMovimiento
  desde?: string
  hasta?: string
  page?: number
  per_page?: number
}

export interface NuevoMovimiento {
  sku: string
  id_bodega: number
  tipo: TipoMovimientoManual
  cantidad: number
  costo_unitario?: number
  motivo: string
  documento_referencia?: string
}

/** Texto opcional: vacío viaja como null. */
const opcional = (texto?: string | null) => (texto?.trim() ? texto.trim() : null)

export const movimientosApi = {
  /** GET /api/movimientos (del más reciente al más antiguo) */
  listar: (f: FiltroMovimientos = {}) => pedir<Paginado<Movimiento>>('GET', '/movimientos', { query: { ...f } }),
  /** GET /api/movimientos/{id} */
  obtener: (id: number) => pedir<Movimiento>('GET', `/movimientos/${id}`),
  /** POST /api/movimientos → 201; ms-inventario publica MovimientoRegistrado y, si aplica, StockBajoUmbral */
  crear: (m: NuevoMovimiento) =>
    pedir<Movimiento>('POST', '/movimientos', {
      cuerpo: {
        sku: m.sku,
        id_bodega: m.id_bodega,
        tipo: m.tipo,
        cantidad: m.cantidad,
        ...(m.costo_unitario !== undefined ? { costo_unitario: m.costo_unitario } : {}),
        motivo: opcional(m.motivo),
        documento_referencia: opcional(m.documento_referencia),
      },
    }),
}

export const kardexApi = {
  /** GET /api/kardex?sku&id_bodega&desde&hasta (obligatorios; AAAA-MM-DD es el día en Colombia) */
  consultar: (f: { sku: string; id_bodega: number; desde: string; hasta: string }) =>
    pedir<Kardex>('GET', '/kardex', { query: { ...f } }),
}

export const trasladosApi = {
  /** GET /api/traslados */
  listar: (f: { sku?: string; desde?: string; hasta?: string; page?: number } = {}) =>
    pedir<Paginado<Traslado>>('GET', '/traslados', { query: { ...f, per_page: 20 } }),
  /** POST /api/traslados → 201 con sus dos movimientos */
  crear: (t: { sku: string; id_bodega_origen: number; id_bodega_destino: number; cantidad: number; motivo?: string }) =>
    pedir<Traslado>('POST', '/traslados', { cuerpo: { ...t, motivo: opcional(t.motivo) } }),
}

export const devolucionesClienteApi = {
  /** GET /api/devoluciones-cliente */
  listar: (f: { sku?: string; page?: number } = {}) =>
    pedir<Paginado<Movimiento>>('GET', '/devoluciones-cliente', { query: { ...f, per_page: 20 } }),
  /** POST /api/devoluciones-cliente → 201 movimiento DEVOLUCION_CLIENTE (RF13) */
  crear: (d: { sku: string; id_bodega: number; cantidad: number; factura_pos: string; motivo: string }) =>
    pedir<Movimiento>('POST', '/devoluciones-cliente', { cuerpo: d }),
}

// ---------- ms-proveedores: /api/proveedores ----------

export const proveedoresApi = {
  /** GET /api/proveedores */
  listar: (f: { q?: string; estado?: Estado; sku?: string; page?: number; per_page?: number } = {}) =>
    pedir<Paginado<Proveedor>>('GET', '/proveedores', { query: { ...f } }),
  /** Todos los proveedores, con sus contactos. */
  todos: () => todas<Proveedor>('/proveedores'),
  /** GET /api/proveedores/{id} */
  obtener: (id: number) => pedir<Proveedor>('GET', `/proveedores/${id}`),
  /** GET /api/proveedores/{id}/productos */
  productos: (id: number) => pedir<ProductoSuministrado[]>('GET', `/proveedores/${id}/productos`),
  /** POST /api/proveedores/{id}/inactivar | /activar */
  cambiarEstado: (id: number, estado: Estado) =>
    pedir<Proveedor>('POST', `/proveedores/${id}/${estado === 'ACTIVO' ? 'activar' : 'inactivar'}`),
  /** PUT /api/proveedores/{id}/productos/{sku}: asocia el producto o reemplaza su precio, días y estado */
  guardarProducto: (id: number, sku: string, d: { precio_compra: number; dias_entrega: number; estado?: Estado }) =>
    pedir<ProductoSuministrado>('PUT', `/proveedores/${id}/productos/${encodeURIComponent(sku)}`, { cuerpo: d }),
  /** DELETE /api/proveedores/{id}/productos/{sku} → 204 */
  eliminarProducto: (id: number, sku: string) =>
    pedir<void>('DELETE', `/proveedores/${id}/productos/${encodeURIComponent(sku)}`),
  /** POST /api/proveedores/{id}/contactos → 201 */
  agregarContacto: (id: number, d: Omit<Contacto, 'id_contacto'>) =>
    pedir<Contacto>('POST', `/proveedores/${id}/contactos`, { cuerpo: d }),
  /** DELETE /api/proveedores/{id}/contactos/{id_contacto} → 204 */
  eliminarContacto: (id: number, id_contacto: number) =>
    pedir<void>('DELETE', `/proveedores/${id}/contactos/${id_contacto}`),
}

// ---------- ms-compras: /api/ordenes-compra, /api/devoluciones-proveedor ----------

// ms-compras nombra algunos campos distinto del contrato (creada_en, cantidad_pedida,
// id_usuario_creador). Se aceptan las dos formas para no depender de cuál llegue.
interface ItemCompras { id_detalle: number; sku?: string; cantidad?: number }
interface DetalleCompras {
  id_detalle: number
  sku: string
  cantidad?: number
  cantidad_pedida?: number
  cantidad_recibida: number
  cantidad_devuelta: number
  precio_unitario: number
}
interface RecepcionCompras { id_recepcion: number; fecha: string; id_usuario: number; observaciones?: string | null; items?: ItemCompras[] }
interface DevolucionCompras {
  id_devolucion: number
  id_orden: number
  numero_orden?: string
  id_proveedor?: number
  fecha: string
  id_usuario: number
  motivo: string
  items?: ItemCompras[]
}
interface OrdenCompras {
  id_orden: number
  numero: string
  id_proveedor: number
  id_bodega_destino: number
  estado: EstadoOrden
  total: number
  creada_en?: string
  fecha_creacion?: string
  actualizada_en?: string | null
  fecha_actualizacion?: string
  aprobada_en?: string | null
  id_usuario_creador?: number
  id_usuario?: number
  id_usuario_aprobador?: number | null
  motivo_anulacion: string | null
  items?: DetalleCompras[]
  recepciones?: RecepcionCompras[]
  devoluciones?: DevolucionCompras[]
}

const aItems = (items: ItemCompras[] = []): ItemMovido[] =>
  items.map((i) => ({ id_detalle: i.id_detalle, cantidad: Number(i.cantidad ?? 0), sku: i.sku }))

const aDetalle = (d: DetalleCompras): DetalleOrden => ({
  id_detalle: d.id_detalle,
  sku: d.sku,
  cantidad: Number(d.cantidad_pedida ?? d.cantidad ?? 0),
  precio_unitario: Number(d.precio_unitario),
  cantidad_recibida: Number(d.cantidad_recibida ?? 0),
  cantidad_devuelta: Number(d.cantidad_devuelta ?? 0),
})

const aRecepcion = (r: RecepcionCompras): Recepcion => ({
  id_recepcion: r.id_recepcion,
  fecha: r.fecha,
  id_usuario: r.id_usuario,
  observaciones: r.observaciones ?? '',
  items: aItems(r.items),
})

const aDevolucion = (d: DevolucionCompras, id_proveedor?: number): DevolucionProveedor => ({
  id_devolucion: d.id_devolucion,
  id_orden: d.id_orden,
  numero_orden: d.numero_orden,
  id_proveedor: d.id_proveedor ?? id_proveedor ?? 0,
  fecha: d.fecha,
  id_usuario: d.id_usuario,
  motivo: d.motivo,
  items: aItems(d.items),
})

function aOrden(o: OrdenCompras): OrdenCompra {
  const creada = o.creada_en ?? o.fecha_creacion ?? ''
  return {
    id_orden: o.id_orden,
    numero: o.numero,
    id_proveedor: o.id_proveedor,
    id_bodega_destino: o.id_bodega_destino,
    estado: o.estado,
    total: Number(o.total),
    fecha_creacion: creada,
    fecha_actualizacion: o.actualizada_en ?? o.fecha_actualizacion ?? creada,
    fecha_aprobacion: o.aprobada_en ?? null,
    id_usuario: o.id_usuario_creador ?? o.id_usuario ?? 0,
    id_usuario_aprobador: o.id_usuario_aprobador ?? null,
    motivo_anulacion: o.motivo_anulacion,
    items: (o.items ?? []).map(aDetalle),
    recepciones: (o.recepciones ?? []).map(aRecepcion),
    devoluciones: (o.devoluciones ?? []).map((d) => aDevolucion(d, o.id_proveedor)),
  }
}

/** Solo viajan los renglones con cantidad: ms-compras rechaza cantidades en cero. */
const conCantidad = (items: ItemCantidad[]) => items.filter((i) => i.cantidad > 0)

export const ordenesApi = {
  /** GET /api/ordenes-compra (las más recientes primero) */
  async listar(f: { estado?: EstadoOrden; id_proveedor?: number; page?: number; per_page?: number } = {}): Promise<Paginado<OrdenCompra>> {
    const r = await pedir<Paginado<OrdenCompras>>('GET', '/ordenes-compra', { query: { ...f } })
    return { data: r.data.map(aOrden), meta: r.meta }
  },
  /** GET /api/ordenes-compra/{id} con ítems, recepciones y devoluciones */
  obtener: async (id: number) => aOrden(await pedir<OrdenCompras>('GET', `/ordenes-compra/${id}`)),
  /** POST /api/ordenes-compra → 201 en BORRADOR; publica OrdenCompraActualizada */
  crear: async (o: { id_proveedor: number; id_bodega_destino: number; items: Array<{ sku: string; cantidad: number; precio_unitario: number }> }) =>
    aOrden(await pedir<OrdenCompras>('POST', '/ordenes-compra', { cuerpo: o })),
  /** POST /api/ordenes-compra/{id}/aprobar */
  aprobar: async (id: number) => aOrden(await pedir<OrdenCompras>('POST', `/ordenes-compra/${id}/aprobar`)),
  /** POST /api/ordenes-compra/{id}/anular */
  anular: async (id: number, motivo: string) => aOrden(await pedir<OrdenCompras>('POST', `/ordenes-compra/${id}/anular`, { cuerpo: { motivo } })),
  /** POST /api/ordenes-compra/{id}/recepciones → publica MercanciaRecibida; devuelve la orden actualizada */
  async recibir(id: number, items: ItemCantidad[], observaciones: string): Promise<OrdenCompra> {
    await pedir('POST', `/ordenes-compra/${id}/recepciones`, { cuerpo: { observaciones: opcional(observaciones), items: conCantidad(items) } })
    return ordenesApi.obtener(id)
  },
  /** POST /api/ordenes-compra/{id}/devoluciones → publica DevolucionProveedorRegistrada (RF13) */
  async devolver(id: number, items: ItemCantidad[], motivo: string): Promise<OrdenCompra> {
    await pedir('POST', `/ordenes-compra/${id}/devoluciones`, { cuerpo: { motivo, items: conCantidad(items) } })
    return ordenesApi.obtener(id)
  },
}

export const devolucionesProveedorApi = {
  /** GET /api/devoluciones-proveedor */
  async listar(f: { id_proveedor?: number; page?: number } = {}): Promise<Paginado<DevolucionProveedor>> {
    const r = await pedir<Paginado<DevolucionCompras>>('GET', '/devoluciones-proveedor', { query: { ...f, per_page: 20 } })
    return { data: r.data.map((d) => aDevolucion(d)), meta: r.meta }
  },
}

// ---------- Búsqueda global ----------

/**
 * Búsqueda de la barra superior. Productos y proveedores usan el filtro q de su
 * servicio; las órdenes y los movimientos no tienen búsqueda por texto en la API,
 * así que se buscan entre los 100 más recientes (o por número exacto: MOV-000123).
 * Cada parte se pide solo si el rol puede verla y un servicio caído no tumba las demás.
 */
export async function buscarTodo(q: string, rol: Rol) {
  const t = q.trim()
  const minus = t.toLowerCase()
  const nada = <T,>(): Promise<T[]> => Promise.resolve([])
  const seguro = <T,>(p: Promise<T[]>) => p.catch(() => [] as T[])
  const numeroMov = /^mov-?0*(\d+)$/i.exec(t)?.[1]
  const [productos, ordenes, movimientos, proveedores] = await Promise.all([
    puedeVer(rol, 'stock') ? seguro(productosApi.listar({ q: t, per_page: 12 }).then((r) => r.data)) : nada<Producto>(),
    puedeVer(rol, 'ordenes')
      ? seguro(ordenesApi.listar({ per_page: 100 }).then((r) => r.data.filter((o) => o.numero.toLowerCase().includes(minus)).slice(0, 12)))
      : nada<OrdenCompra>(),
    puedeVer(rol, 'movimientos')
      ? seguro(numeroMov
        ? movimientosApi.obtener(Number(numeroMov)).then((m) => [m])
        : movimientosApi.listar({ per_page: 100 }).then((r) => r.data.filter((m) => m.documento_referencia?.toLowerCase().includes(minus)).slice(0, 12)))
      : nada<Movimiento>(),
    puedeVer(rol, 'proveedores') ? seguro(proveedoresApi.listar({ q: t, per_page: 8 }).then((r) => r.data)) : nada<Proveedor>(),
  ])
  return { productos, ordenes, movimientos, proveedores }
}

// ---------- ms-reportes: /api/dashboard, /api/reportes/* ----------

const lista = <T,>(r: T[] | { data: T[] }): T[] => (Array.isArray(r) ? r : r.data ?? [])

/**
 * Mientras ms-reportes no esté en línea, el gateway responde 503 (o 404 si el servicio
 * existe sin la ruta). Se convierte en un aviso claro; el resto de la interfaz sigue igual.
 */
async function reporte<T>(ruta: string, query: Record<string, string | number | undefined>): Promise<T> {
  try {
    return await pedir<T>('GET', ruta, { query })
  } catch (e) {
    if (e instanceof ApiError && [404, 502, 503, 504].includes(e.status)) {
      throw new ApiError(503, 'REPORTES_NO_DISPONIBLE', 'Los indicadores y reportes aparecerán cuando ms-reportes esté en línea. El rack, el stock y los movimientos siguen funcionando.')
    }
    throw e
  }
}

export const reportesApi = {
  /** GET /api/dashboard (RF14) */
  dashboard: (id_bodega?: number) => reporte<Dashboard>('/dashboard', { id_bodega }),
  /** GET /api/reportes/valorizacion?agrupar=producto|categoria|bodega */
  valorizacion: async (agrupar: AgruparValorizacion, id_bodega?: number) =>
    lista(await reporte<FilaValorizacion[] | { data: FilaValorizacion[] }>('/reportes/valorizacion', { agrupar, id_bodega })),
  /** GET /api/reportes/rotacion?desde&hasta&id_bodega&top */
  rotacion: (f: { desde: string; hasta: string; id_bodega?: number; top?: number }) =>
    reporte<{ mayor_rotacion: ItemRotacion[]; menor_rotacion: ItemRotacion[] }>('/reportes/rotacion', f),
  /** GET /api/reportes/stock-bajo?id_bodega */
  stockBajo: async (id_bodega?: number) => lista(await reporte<AlertaStock[] | { data: AlertaStock[] }>('/reportes/stock-bajo', { id_bodega })),
}

// ---------- ms-notificaciones: /api/notificaciones ----------

// ms-notificaciones guarda id_notificacion, rol_destino en minúsculas, los datos del
// evento dentro de "datos" y la fecha como creada_en o actualizada_en.
interface NotificacionServicio {
  id_notificacion?: string
  id?: string
  titulo: string
  mensaje: string
  rol_destino: string
  leida: boolean
  datos?: { sku?: string; id_bodega?: number } | null
  creada_en?: string
  actualizada_en?: string
  fecha?: string
  sku?: string | null
  id_bodega?: number | null
}

const aNotificacion = (n: NotificacionServicio): Notificacion => ({
  id: n.id_notificacion ?? n.id ?? '',
  titulo: n.titulo,
  mensaje: n.mensaje,
  rol_destino: rolDeCodigo(n.rol_destino),
  leida: !!n.leida,
  fecha: n.actualizada_en ?? n.creada_en ?? n.fecha ?? '',
  sku: n.datos?.sku ?? n.sku ?? null,
  id_bodega: n.datos?.id_bodega ?? n.id_bodega ?? null,
})

export const notificacionesApi = {
  /** GET /api/notificaciones?leida; el servicio filtra por el rol del usuario (el administrador ve todas) */
  async listar(f: { leida?: boolean; page?: number } = {}): Promise<Paginado<Notificacion>> {
    const r = await pedir<Paginado<NotificacionServicio>>('GET', '/notificaciones', { query: { ...f, per_page: 50 } })
    return { data: r.data.map(aNotificacion), meta: r.meta }
  },
  /** POST /api/notificaciones/{id}/leida */
  marcarLeida: async (id: string) => aNotificacion(await pedir<NotificacionServicio>('POST', `/notificaciones/${encodeURIComponent(id)}/leida`)),
}

// ---------- Altas de maestros (POST de cada servicio) ----------

export const altasApi = {
  /** POST /api/usuarios → 201 (gateway) */
  usuario: async (u: { nombre: string; email: string; password: string; id_rol: number }) =>
    aUsuario(await pedir<UsuarioGateway>('POST', '/usuarios', { cuerpo: u })),
  /** POST /api/productos → 201 (ms-productos) */
  producto: (p: { sku: string; nombre: string; descripcion: string; marca: string; id_categoria: number; unidad_medida: UnidadMedida; precio_venta: number; stock_minimo: number }) =>
    pedir<Producto>('POST', '/productos', { cuerpo: { ...p, descripcion: opcional(p.descripcion) } }),
  /** POST /api/categorias → 201 (ms-productos) */
  categoria: (c: { nombre: string; descripcion: string; id_categoria_padre: number | null }) =>
    pedir<Categoria>('POST', '/categorias', { cuerpo: { ...c, descripcion: opcional(c.descripcion) } }),
  /** POST /api/proveedores → 201 (ms-proveedores) */
  proveedor: (p: { nit: string; razon_social: string; telefono: string; email: string; direccion: string }) =>
    pedir<Proveedor>('POST', '/proveedores', { cuerpo: p }),
  /** POST /api/bodegas → 201 (ms-inventario) */
  bodega: (b: { codigo: string; nombre: string; direccion: string }) => pedir<Bodega>('POST', '/bodegas', { cuerpo: b }),
}
