// Carga los datos maestros al entrar a la aplicación y los vuelve a leer cuando se
// crea un producto, una categoría, un proveedor o una bodega, o cuando aparece un
// código que no estaba cargado. Las pantallas que muestran nombres usan useMaestros
// para volver a pintarse con la versión nueva.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { LogOut, RotateCcw } from 'lucide-react'
import { cargarMaestros, suscribirFaltantes } from '../api/maestros'
import { useSesion, useUsuario } from '../auth/Sesion'
import { LogoEstiba } from '../componentes/Marca'
import { ErrorCaja } from '../componentes/ui'

interface ContextoMaestros {
  version: number
  /** Servicios que no respondieron en la última carga (proveedores, usuarios o roles). */
  fallas: string[]
  recargar: () => Promise<void>
}

const Contexto = createContext<ContextoMaestros | null>(null)

export function ProveedorMaestros({ children }: { children: ReactNode }) {
  const usuario = useUsuario()
  const { cerrar } = useSesion()
  const [version, setVersion] = useState(0)
  const [fallas, setFallas] = useState<string[]>([])
  const [error, setError] = useState<Error | null>(null)
  const esAdmin = usuario.rol === 'ADMINISTRADOR'

  const recargar = useCallback(async () => {
    setFallas(await cargarMaestros({ id: usuario.id, nombre: usuario.nombre }, esAdmin))
    setError(null)
    setVersion((v) => v + 1)
  }, [usuario.id, usuario.nombre, esAdmin])

  useEffect(() => {
    recargar().catch((e: Error) => setError(e))
  }, [recargar])

  useEffect(() => suscribirFaltantes(() => { recargar().catch(() => {}) }), [recargar])

  const valor = useMemo(() => ({ version, fallas, recargar }), [version, fallas, recargar])

  if (version === 0) {
    return (
      <div className="carga-inicial">
        <LogoEstiba tamano={56} />
        {error ? (
          <div className="carga-inicial-error">
            <ErrorCaja error={error} />
            <div className="acciones-separadas">
              <button type="button" className="btn btn-pri" onClick={() => { setError(null); recargar().catch((e: Error) => setError(e)) }}><RotateCcw size={18} aria-hidden />Reintentar</button>
              <button type="button" className="btn btn-fantasma" onClick={() => { cerrar() }}><LogOut size={18} aria-hidden />Cerrar sesión</button>
            </div>
          </div>
        ) : (
          <p role="status">Cargando productos, categorías y bodegas…</p>
        )}
      </div>
    )
  }
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

export function useMaestros(): ContextoMaestros {
  const c = useContext(Contexto)
  if (!c) throw new Error('useMaestros debe usarse dentro de ProveedorMaestros')
  return c
}
