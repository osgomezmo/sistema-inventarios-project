// Bodega activa: el contexto en el que trabaja la persona (se elige en la barra superior).
import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import { bodegas } from '../api/mock/maestros'
import { guardar, leer } from '../lib/almacen'
import type { Bodega } from '../api/types'

const CLAVE = 'estiba.bodega'

interface ContextoBodega {
  idBodega: number
  bodega: Bodega
  cambiar: (id: number) => void
  activas: Bodega[]
}

const Contexto = createContext<ContextoBodega | null>(null)
const activas = bodegas.filter((b) => b.estado === 'ACTIVO')

export function ProveedorBodega({ children }: { children: ReactNode }) {
  const [idBodega, setId] = useState<number>(() => {
    const guardada = leer<number>(CLAVE)
    return activas.some((b) => b.id_bodega === guardada) ? (guardada as number) : 2
  })
  const valor = useMemo<ContextoBodega>(() => ({
    idBodega,
    bodega: activas.find((b) => b.id_bodega === idBodega)!,
    cambiar: (id: number) => { guardar(CLAVE, id); setId(id) },
    activas,
  }), [idBodega])
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

export function useBodega(): ContextoBodega {
  const c = useContext(Contexto)
  if (!c) throw new Error('useBodega debe usarse dentro de ProveedorBodega')
  return c
}
