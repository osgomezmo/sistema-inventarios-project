// Matriz de permisos por rol (tabla 4 de la entrega 2). El gateway es quien la aplica
// (401/403); la interfaz la usa solo para no mostrar acciones que el rol no puede hacer.
import type { Rol } from '../api/types'

export type Acceso = 'editar' | 'ver' | null

export type Operacion =
  | 'usuarios'
  | 'catalogo'
  | 'bodegas'
  | 'stock'
  | 'movimientos'
  | 'devolucionCliente'
  | 'proveedores'
  | 'ordenes'
  | 'aprobarOrdenes'
  | 'recibirMercancia'
  | 'devolucionProveedor'
  | 'reportes'
  | 'notificaciones'

const E = 'editar' as const
const V = 'ver' as const

const matriz: Record<Operacion, Record<Rol, Acceso>> = {
  usuarios: { ADMINISTRADOR: E, JEFE_BODEGA: null, COMPRAS: null, GERENTE: null },
  catalogo: { ADMINISTRADOR: E, JEFE_BODEGA: V, COMPRAS: V, GERENTE: V },
  bodegas: { ADMINISTRADOR: E, JEFE_BODEGA: E, COMPRAS: V, GERENTE: V },
  stock: { ADMINISTRADOR: V, JEFE_BODEGA: V, COMPRAS: V, GERENTE: V },
  movimientos: { ADMINISTRADOR: E, JEFE_BODEGA: E, COMPRAS: null, GERENTE: V },
  devolucionCliente: { ADMINISTRADOR: E, JEFE_BODEGA: E, COMPRAS: null, GERENTE: V },
  proveedores: { ADMINISTRADOR: E, JEFE_BODEGA: V, COMPRAS: E, GERENTE: V },
  ordenes: { ADMINISTRADOR: E, JEFE_BODEGA: V, COMPRAS: E, GERENTE: V },
  aprobarOrdenes: { ADMINISTRADOR: E, JEFE_BODEGA: null, COMPRAS: null, GERENTE: E },
  recibirMercancia: { ADMINISTRADOR: E, JEFE_BODEGA: E, COMPRAS: null, GERENTE: null },
  devolucionProveedor: { ADMINISTRADOR: E, JEFE_BODEGA: E, COMPRAS: E, GERENTE: null },
  reportes: { ADMINISTRADOR: V, JEFE_BODEGA: V, COMPRAS: V, GERENTE: V },
  notificaciones: { ADMINISTRADOR: V, JEFE_BODEGA: V, COMPRAS: V, GERENTE: V },
}

export const acceso = (rol: Rol, op: Operacion): Acceso => matriz[op][rol]
export const puedeVer = (rol: Rol, op: Operacion) => acceso(rol, op) !== null
export const puedeEditar = (rol: Rol, op: Operacion) => acceso(rol, op) === 'editar'

export const nombreRol: Record<Rol, string> = {
  ADMINISTRADOR: 'Administrador',
  JEFE_BODEGA: 'Jefe de bodega',
  COMPRAS: 'Compras',
  GERENTE: 'Gerente',
}
