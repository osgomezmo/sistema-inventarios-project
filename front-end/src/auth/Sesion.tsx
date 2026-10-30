// Sesión del usuario: el token de Sanctum y el usuario que devuelve POST /api/auth/login.
// SEG-7 (guía técnica): el token se guarda en localStorage por simplicidad.
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router'
import type { RespuestaLogin } from '../api/types'
import { auth } from '../api/cliente'
import { guardar, leer } from '../lib/almacen'
import { puedeVer, type Operacion } from './permisos'
import { SinPermiso } from '../paginas/Errores'

const CLAVE = 'estiba.sesion'

interface ContextoSesion {
  sesion: RespuestaLogin | null
  iniciar: (s: RespuestaLogin) => void
  cerrar: () => Promise<void>
}

const Contexto = createContext<ContextoSesion | null>(null)

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<RespuestaLogin | null>(() => leer<RespuestaLogin>(CLAVE))

  const iniciar = useCallback((s: RespuestaLogin) => {
    guardar(CLAVE, s)
    setSesion(s)
  }, [])

  const cerrar = useCallback(async () => {
    await auth.logout()
    guardar(CLAVE, null)
    setSesion(null)
  }, [])

  const valor = useMemo(() => ({ sesion, iniciar, cerrar }), [sesion, iniciar, cerrar])
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

export function useSesion(): ContextoSesion {
  const c = useContext(Contexto)
  if (!c) throw new Error('useSesion debe usarse dentro de ProveedorSesion')
  return c
}

/** Usuario autenticado; solo se usa dentro de rutas protegidas. */
export function useUsuario(): RespuestaLogin['usuario'] {
  const { sesion } = useSesion()
  if (!sesion) throw new Error('No hay sesión activa')
  return sesion.usuario
}

/** Ruta protegida: sin token, vuelve al inicio de sesión (equivale a un 401). */
export function RequiereSesion() {
  const { sesion } = useSesion()
  const ubicacion = useLocation()
  if (!sesion) return <Navigate to="/ingresar" replace state={{ desde: ubicacion.pathname + ubicacion.search }} />
  return <Outlet />
}

/** Pantalla solo para los roles con permiso (equivale a un 403 del gateway). */
export function ConPermiso({ op, children }: { op: Operacion; children: ReactNode }) {
  const usuario = useUsuario()
  return puedeVer(usuario.rol, op) ? <>{children}</> : <SinPermiso />
}
