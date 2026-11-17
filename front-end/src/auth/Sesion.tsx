// Sesión del usuario: el token personal de Sanctum y el usuario que devuelve
// POST /api/auth/login. SEG-7 (guía técnica): el token se guarda en localStorage por
// simplicidad. Si el gateway lo rechaza (vencido, revocado o usuario inactivado), la
// sesión se cierra y se vuelve a la pantalla de ingreso.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router'
import type { RespuestaLogin } from '../api/types'
import { auth } from '../api/cliente'
import { configurarSesion } from '../api/http'
import { guardar, leer } from '../lib/almacen'
import { puedeVer, type Operacion } from './permisos'
import { SinPermiso } from '../paginas/Errores'
import { ProveedorMaestros } from '../contexto/Maestros'
import { ProveedorBodega } from '../contexto/Bodega'

const CLAVE = 'estiba.sesion'

interface ContextoSesion {
  sesion: RespuestaLogin | null
  /** true cuando el gateway rechazó el token y la sesión se cerró sola. */
  expirada: boolean
  iniciar: (s: RespuestaLogin) => void
  cerrar: () => Promise<void>
}

const Contexto = createContext<ContextoSesion | null>(null)

function sesionGuardada(): RespuestaLogin | null {
  const s = leer<RespuestaLogin>(CLAVE)
  // Una sesión de la plantilla con datos de ejemplo no tiene un token de Sanctum (id|texto).
  const valida = !!s?.token && /^\d+\|/.test(s.token) && !!s.usuario?.rol
  configurarSesion(valida ? s!.token : null)
  return valida ? s : null
}

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<RespuestaLogin | null>(sesionGuardada)
  const [expirada, setExpirada] = useState(false)

  const olvidar = useCallback(() => {
    configurarSesion(null)
    guardar(CLAVE, null)
    setSesion(null)
  }, [])

  useEffect(() => {
    configurarSesion(sesion?.token ?? null, () => { setExpirada(true); olvidar() })
  }, [sesion, olvidar])

  const iniciar = useCallback((s: RespuestaLogin) => {
    configurarSesion(s.token)
    guardar(CLAVE, s)
    setExpirada(false)
    setSesion(s)
  }, [])

  const cerrar = useCallback(async () => {
    // Revoca el token en el gateway; si ya no servía o no hay red, igual se olvida aquí.
    try { await auth.logout() } catch { /* sesión local cerrada de todos modos */ }
    setExpirada(false)
    olvidar()
  }, [olvidar])

  const valor = useMemo(() => ({ sesion, expirada, iniciar, cerrar }), [sesion, expirada, iniciar, cerrar])
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

/**
 * Ruta protegida: sin token vuelve al inicio de sesión (equivale a un 401). Con sesión,
 * carga los datos maestros y la bodega activa antes de mostrar cualquier pantalla.
 */
export function RequiereSesion() {
  const { sesion } = useSesion()
  const ubicacion = useLocation()
  if (!sesion) return <Navigate to="/ingresar" replace state={{ desde: ubicacion.pathname + ubicacion.search }} />
  return (
    <ProveedorMaestros key={sesion.token}>
      <ProveedorBodega>
        <Outlet />
      </ProveedorBodega>
    </ProveedorMaestros>
  )
}

/** Pantalla solo para los roles con permiso (equivale a un 403 del gateway). */
export function ConPermiso({ op, children }: { op: Operacion; children: ReactNode }) {
  const usuario = useUsuario()
  return puedeVer(usuario.rol, op) ? <>{children}</> : <SinPermiso />
}
