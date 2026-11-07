// Tipos de las respuestas de la API pública del gateway (/api/...).
// Siguen los contratos del capítulo 4 de la entrega 2: nombres de campos,
// estados y tipos de movimiento tal como viajan en el JSON.

// ---------- Convenciones comunes (sección 4.1) ----------

export type Estado = 'ACTIVO' | 'INACTIVO'

export interface MetaPaginacion {
  page: number
  per_page: number
  total: number
}

export interface Paginado<T> {
  data: T[]
  meta: MetaPaginacion
}

export interface ErrorApi {
  error: {
    codigo: string
    mensaje: string
    detalles?: Record<string, string[]>
  }
}

// ---------- API Gateway: identidad y acceso (tabla 5) ----------

export type Rol = 'ADMINISTRADOR' | 'JEFE_BODEGA' | 'COMPRAS' | 'GERENTE'

export interface Usuario {
  id: number
  nombre: string
  email: string
  rol: Rol
  estado: Estado
  ultimo_acceso: string | null
}

/** POST /api/auth/login → 200 */
export interface RespuestaLogin {
  token: string
  usuario: Pick<Usuario, 'id' | 'nombre' | 'email' | 'rol'>
}

/** GET /api/roles → 200 roles con sus permisos */
export interface RolConPermisos {
  id_rol: number
  nombre: Rol
  permisos: string[]
}

// ---------- ms-productos (tabla 6) ----------

export type UnidadMedida = 'UNIDAD' | 'KILO' | 'LITRO'

export interface Categoria {
  id_categoria: number
  nombre: string
  descripcion: string
  id_categoria_padre: number | null
  estado: Estado
  subcategorias?: Categoria[]
}

export interface Producto {
  id_producto: number
  sku: string
  nombre: string
  descripcion: string
  marca: string
  id_categoria: number
  unidad_medida: UnidadMedida
  precio_venta: number
  stock_minimo: number
  estado: Estado
}

// ---------- ms-inventario (tabla 7) ----------

export interface Bodega {
  id_bodega: number
  codigo: string
  nombre: string
  direccion: string
  estado: Estado
}

/** Una fila de GET /api/stock: saldo de un producto en una bodega. */
export interface Saldo {
  sku: string
  id_bodega: number
  cantidad: number
  costo_promedio: number
  valor: number
  stock_minimo: number
  bajo_minimo: boolean
}

/** GET /api/stock/{sku} → saldo por bodega y consolidado (RF05). */
export interface StockProducto {
  sku: string
  por_bodega: Array<Pick<Saldo, 'id_bodega' | 'cantidad' | 'costo_promedio' | 'valor'>>
  total: { cantidad: number; valor: number }
}

export type TipoMovimiento =
  | 'ENTRADA_COMPRA'
  | 'AJUSTE_POSITIVO'
  | 'TRASLADO_ENTRADA'
  | 'DEVOLUCION_CLIENTE'
  | 'SALIDA'
  | 'AJUSTE_NEGATIVO'
  | 'TRASLADO_SALIDA'
  | 'DEVOLUCION_PROVEEDOR'

/** Tipos que se registran por POST /api/movimientos; el resto llega por eventos o por su propio endpoint. */
export type TipoMovimientoManual = 'SALIDA' | 'AJUSTE_POSITIVO' | 'AJUSTE_NEGATIVO'

export interface Movimiento {
  id_movimiento: number
  sku: string
  id_bodega: number
  tipo: TipoMovimiento
  cantidad: number
  costo_unitario: number
  saldo_resultante: number
  costo_promedio: number
  valor_resultante: number
  motivo: string | null
  documento_referencia: string | null
  id_usuario: number
  fecha: string
}

/** GET /api/kardex → saldo inicial, movimientos y saldo final en cantidad y valor (RF10). */
export interface Kardex {
  sku: string
  id_bodega: number
  desde: string
  hasta: string
  saldo_inicial: { cantidad: number; valor: number }
  movimientos: Movimiento[]
  saldo_final: { cantidad: number; valor: number }
}

export interface Traslado {
  id_traslado: number
  sku: string
  id_bodega_origen: number
  id_bodega_destino: number
  cantidad: number
  motivo: string | null
  id_usuario: number
  fecha: string
  movimientos: { salida: number; entrada: number }
}

// ---------- ms-proveedores (tabla 8) ----------

export interface Contacto {
  id_contacto: number
  nombre: string
  cargo: string
  telefono: string
  email: string
}

export interface Proveedor {
  id_proveedor: number
  nit: string
  razon_social: string
  telefono: string
  email: string
  direccion: string
  estado: Estado
  contactos: Contacto[]
}

/** GET /api/proveedores/{id}/productos */
export interface ProductoSuministrado {
  sku: string
  precio_compra: number
  dias_entrega: number
  estado: Estado
}

// ---------- ms-compras (tabla 9) ----------

export type EstadoOrden = 'BORRADOR' | 'APROBADA' | 'RECIBIDA_PARCIAL' | 'RECIBIDA' | 'ANULADA'

export interface DetalleOrden {
  id_detalle: number
  sku: string
  cantidad: number
  precio_unitario: number
  cantidad_recibida: number
  cantidad_devuelta: number
}

export interface ItemCantidad {
  id_detalle: number
  cantidad: number
}

export interface Recepcion {
  id_recepcion: number
  fecha: string
  id_usuario: number
  observaciones: string
  items: ItemCantidad[]
}

export interface DevolucionProveedor {
  id_devolucion: number
  id_orden: number
  id_proveedor: number
  fecha: string
  id_usuario: number
  motivo: string
  items: ItemCantidad[]
}

export interface OrdenCompra {
  id_orden: number
  numero: string
  id_proveedor: number
  id_bodega_destino: number
  estado: EstadoOrden
  fecha_creacion: string
  fecha_actualizacion: string
  id_usuario: number
  total: number
  motivo_anulacion: string | null
  items: DetalleOrden[]
  recepciones: Recepcion[]
  devoluciones: DevolucionProveedor[]
}

// ---------- ms-reportes (tabla 10) ----------

export interface ItemRotacion {
  sku: string
  nombre: string
  unidades_salida: number
  rotacion: number
}

/** GET /api/dashboard (RF14). Los movimientos recientes salen de GET /api/movimientos?per_page=10. */
export interface Dashboard {
  valor_total_inventario: number
  productos_stock_bajo: number
  ordenes_pendientes: number
  mayor_rotacion: ItemRotacion[]
  menor_rotacion: ItemRotacion[]
}

export type AgruparValorizacion = 'producto' | 'categoria' | 'bodega'

export interface FilaValorizacion {
  clave: string
  nombre: string
  cantidad: number
  valor: number
}

export interface AlertaStock {
  sku: string
  id_bodega: number
  saldo: number
  stock_minimo: number
  fecha: string
}

// ---------- ms-notificaciones (tabla 11) ----------

export interface Notificacion {
  id: string
  titulo: string
  mensaje: string
  rol_destino: Rol
  leida: boolean
  fecha: string
  sku: string | null
  id_bodega: number | null
}
