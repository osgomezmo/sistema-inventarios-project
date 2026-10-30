import { Link } from 'react-router'
import { MapPinOff, ShieldX } from 'lucide-react'
import { Vacio } from '../componentes/ui'

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
