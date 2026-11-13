import { Link, useRouteError } from 'react-router'
import { MapPinOff, RotateCcw, ShieldX, TriangleAlert } from 'lucide-react'
import { Vacio } from '../componentes/ui'

/** Pantalla de error de ruta: si una pantalla falla, se muestra esto en lugar de una página en blanco. */
export function ErrorDePantalla() {
  const error = useRouteError() as Error | undefined
  return (
    <div style={{ minHeight: '100dvh', display: 'grid', placeItems: 'center', padding: 24 }}>
      <div className="panel" style={{ maxWidth: 560 }}>
        <Vacio titulo="Esta pantalla tuvo un problema" icono={<TriangleAlert size={44} aria-hidden />}
          accion={<div className="acciones-separadas"><button type="button" className="btn btn-pri" onClick={() => window.location.reload()}><RotateCcw size={18} aria-hidden />Recargar</button><a className="btn" href="/">Ir al dashboard</a></div>}>
          Tus datos guardados no se pierden por esto. Recarga la página; si vuelve a pasar, avisa al equipo con este detalle: {error?.message ?? 'error desconocido'}.
        </Vacio>
      </div>
    </div>
  )
}

export function SinPermiso() {
  return (
    <div className="panel">
      <Vacio titulo="Tu rol no tiene acceso a esta pantalla" icono={<ShieldX size={44} aria-hidden />} accion={<Link className="btn" to="/">Volver al dashboard</Link>}>
        Si necesitas entrar, pide al administrador que revise tu rol en Usuarios y roles.
      </Vacio>
    </div>
  )
}

export function NoEncontrado() {
  return (
    <div className="panel">
      <Vacio titulo="Esta ubicación no existe" icono={<MapPinOff size={44} aria-hidden />} accion={<Link className="btn btn-pri" to="/">Ir al dashboard</Link>}>
        Revisa la dirección o vuelve al inicio para seguir trabajando.
      </Vacio>
    </div>
  )
}
