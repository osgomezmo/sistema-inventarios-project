// Bodega activa: el contexto en el que trabaja la persona (se elige en la barra superior).
// Las bodegas salen de los maestros que se leen del gateway al iniciar sesión.
import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import { bodegas } from '../api/maestros'
import { guardar, leer } from '../lib/almacen'
import type { Bodega } from '../api/types'
import { useMaestros } from './Maestros'

const CLAVE = 'estiba.bodega'

/** Sin bodegas activas (sistema recién instalado) las pantallas muestran listas vacías. */
const SIN_BODEGA: Bodega = { id_bodega: 0, codigo: '—', nombre: 'Sin bodegas activas', direccion: '', estado: 'INACTIVO' }

interface ContextoBodega {
  idBodega: number
  bodega: Bodega
  cambiar: (id: number) => void
  activas: Bodega[]
  /** Vuelve a leer las bodegas después de crear o inactivar una. */
  refrescar: () => Promise<void>
}

const Contexto = createContext<ContextoBodega | null>(null)

export function ProveedorBodega({ children }: { children: ReactNode }) {
  const { version, recargar } = useMaestros()
  const activas = useMemo(() => bodegas.filter((b) => b.estado === 'ACTIVO'), [version]) // eslint-disable-line react-hooks/exhaustive-deps
  const [elegida, setElegida] = useState<number | null>(() => leer<number>(CLAVE))
  const bodega = activas.find((b) => b.id_bodega === elegida) ?? activas[0] ?? SIN_BODEGA
  const valor = useMemo<ContextoBodega>(() => ({
    idBodega: bodega.id_bodega,
    bodega,
    cambiar: (id: number) => { guardar(CLAVE, id); setElegida(id) },
    activas,
    refrescar: recargar,
  }), [bodega, activas, recargar])
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

export function useBodega(): ContextoBodega {
  const c = useContext(Contexto)
  if (!c) throw new Error('useBodega debe usarse dentro de ProveedorBodega')
  return c
}
