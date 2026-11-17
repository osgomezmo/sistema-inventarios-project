// Datos maestros en memoria: productos, categorías, bodegas, proveedores y, para el
// administrador, usuarios y roles. Se leen del gateway al iniciar sesión (ver
// contexto/Maestros.tsx) para que las tablas muestren nombres y unidades sin pedir
// cada SKU o cada bodega al servidor. Si aparece un código que no está cargado
// (lo creó otra persona después), se usa un sustituto y se pide recargar.
import type { Bodega, Categoria, Producto, Proveedor, RolConPermisos } from './types'
import { bodegasApi, categoriasApi, productosApi, proveedoresApi, rolesApi, usuariosApi } from './cliente'

export const productos: Producto[] = []
/** Planas: raíces y subcategorías. */
export const categorias: Categoria[] = []
export const bodegas: Bodega[] = []
export const proveedores: Proveedor[] = []
export const roles: RolConPermisos[] = []

export const productoPorSku = new Map<string, Producto>()
export const categoriaPorId = new Map<number, Categoria>()
export const bodegaPorId = new Map<number, Bodega>()
export const proveedorPorId = new Map<number, Proveedor>()
export const usuarioPorId = new Map<number, { id: number; nombre: string }>()

function reemplazar<T>(lista: T[], nuevos: T[]) {
  lista.length = 0
  for (const x of nuevos) lista.push(x)
}

function indexar<K, V>(mapa: Map<K, V>, filas: V[], clave: (v: V) => K) {
  mapa.clear()
  for (const f of filas) mapa.set(clave(f), f)
}

// ---------- Avisos de códigos que faltan ----------

let alFaltar: (() => void) | null = null
let ultimoAviso = 0

/** El proveedor de maestros se suscribe para recargar cuando falta un código. */
export function suscribirFaltantes(oyente: () => void) {
  alFaltar = oyente
  return () => { if (alFaltar === oyente) alFaltar = null }
}

function faltante() {
  const ahora = Date.now()
  if (ahora - ultimoAviso < 30_000) return
  ultimoAviso = ahora
  queueMicrotask(() => alFaltar?.())
}

// ---------- Consultas con sustituto ----------

export function producto(sku: string): Producto {
  const p = productoPorSku.get(sku)
  if (p) return p
  faltante()
  return { id_producto: 0, sku, nombre: sku, descripcion: null, marca: '—', id_categoria: 0, unidad_medida: 'UNIDAD', precio_venta: 0, stock_minimo: 0, estado: 'ACTIVO' }
}

export function bodega(id: number): Bodega {
  const b = bodegaPorId.get(id)
  if (b) return b
  faltante()
  return { id_bodega: id, codigo: `#${id}`, nombre: `Bodega ${id}`, direccion: '', estado: 'ACTIVO' }
}

export function proveedor(id: number): Proveedor {
  const p = proveedorPorId.get(id)
  if (p) return p
  faltante()
  return { id_proveedor: id, nit: '', razon_social: `Proveedor ${id}`, telefono: '', email: '', direccion: '', estado: 'ACTIVO', contactos: [] }
}

/** Nombre de quien registró un documento. Solo el administrador puede listar usuarios. */
export const nombreUsuario = (id: number) => usuarioPorId.get(id)?.nombre ?? `Usuario #${id}`

const SIN_CATEGORIA: Categoria = { id_categoria: 0, nombre: 'Sin categoría', descripcion: null, id_categoria_padre: null, estado: 'ACTIVO' }

export function categoriaRaiz(id_categoria: number): Categoria {
  let c = categoriaPorId.get(id_categoria)
  if (!c) return SIN_CATEGORIA
  for (let i = 0; i < 5 && c.id_categoria_padre !== null; i++) {
    const padre = categoriaPorId.get(c.id_categoria_padre)
    if (!padre) break
    c = padre
  }
  return c
}

export const nombreCategoria = (id: number) => categoriaPorId.get(id)?.nombre ?? SIN_CATEGORIA.nombre

// ---------- Carga ----------

/**
 * Lee los maestros. Productos, categorías y bodegas son indispensables (sin ellos no
 * hay rack ni tablas); proveedores, usuarios y roles se toleran caídos.
 */
export async function cargarMaestros(usuario: { id: number; nombre: string }, esAdmin: boolean): Promise<string[]> {
  const [prods, raices, bods] = await Promise.all([productosApi.todos(), categoriasApi.listar(), bodegasApi.listar()])
  reemplazar(productos, prods)
  indexar(productoPorSku, prods, (p) => p.sku)
  const planas = raices.flatMap((r) => [{ ...r, subcategorias: undefined }, ...(r.subcategorias ?? [])])
  reemplazar(categorias, planas)
  indexar(categoriaPorId, planas, (c) => c.id_categoria)
  reemplazar(bodegas, bods)
  indexar(bodegaPorId, bods, (b) => b.id_bodega)

  const fallas: string[] = []
  const [provs, usuarios, listaRoles] = await Promise.allSettled([
    proveedoresApi.todos(),
    esAdmin ? usuariosApi.todos() : Promise.resolve([]),
    esAdmin ? rolesApi.listar() : Promise.resolve([]),
  ])
  if (provs.status === 'fulfilled') {
    reemplazar(proveedores, provs.value)
    indexar(proveedorPorId, provs.value, (p) => p.id_proveedor)
  } else fallas.push('proveedores')
  usuarioPorId.clear()
  if (usuarios.status === 'fulfilled') for (const u of usuarios.value) usuarioPorId.set(u.id, u)
  else fallas.push('usuarios')
  usuarioPorId.set(usuario.id, usuario)
  if (listaRoles.status === 'fulfilled') reemplazar(roles, listaRoles.value)
  else fallas.push('roles')
  return fallas
}
