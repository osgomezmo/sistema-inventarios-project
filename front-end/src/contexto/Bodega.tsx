// Bodega activa: el contexto en el que trabaja la persona (se elige en la barra superior).
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { bodegas } from '../api/mock/maestros'
import { guardar, leer } from '../lib/almacen'
import type { Bodega } from '../api/types'

const CLAVE = 'estiba.bodega'

interface ContextoBodega {
  idBodega: number
  bodega: Bodega
  cambiar: (id: number) => void
  activas: Bodega[]
  /** Vuelve a leer las bodegas después de crear o inactivar una. */
  refrescar: () => void
}

const Contexto = createContext<ContextoBodega | null>(null)

export function ProveedorBodega({ children }: { children: ReactNode }) {
  const [version, setVersion] = useState(0)
  const activas = useMemo(() => bodegas.filter((b) => b.estado === 'ACTIVO'), [version]) // eslint-disable-line react-hooks/exhaustive-deps
  const [idBodega, setId] = useState<number>(() => {
    const guardada = leer<number>(CLAVE)
    return bodegas.some((b) => b.id_bodega === guardada && b.estado === 'ACTIVO') ? (guardada as number) : 2
  })
  const refrescar = useCallback(() => setVersion((v) => v + 1), [])
  const valor = useMemo<ContextoBodega>(() => ({
    idBodega,
    bodega: activas.find((b) => b.id_bodega === idBodega) ?? activas[0],
    cambiar: (id: number) => { guardar(CLAVE, id); setId(id) },
    activas,
    refrescar,
  }), [idBodega, activas, refrescar])
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

export function useBodega(): ContextoBodega {
  const c = useContext(Contexto)
  if (!c) throw new Error('useBodega debe usarse dentro de ProveedorBodega')
  return c
}
