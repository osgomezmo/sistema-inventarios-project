import { useMemo, useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { auth } from '../api/cliente'
import { usuarios } from '../api/mock/maestros'
import { saldosActuales } from '../api/mock/simulacion'
import { useSesion } from '../auth/Sesion'
import { nombreRol } from '../auth/permisos'
import { LogoEstiba } from '../componentes/Marca'
import { BotonEnvio, Campo, ErrorCaja, erroresCampo } from '../componentes/ui'
import { RackBodega } from '../tres/RackDiferido'

export function Ingreso() {
  const { sesion, iniciar } = useSesion()
  const navegar = useNavigate()
  const ubicacion = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const saldosPortada = useMemo(() => saldosActuales().filter((s) => s.id_bodega === 1), [])

  if (sesion) return <Navigate to="/" replace />
  const destino = (ubicacion.state as { desde?: string } | null)?.desde ?? '/'
  const campos = erroresCampo(error)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      iniciar(await auth.login(email, password))
      navegar(destino, { replace: true })
    } catch (err) {
      setError(err as Error)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="ingreso">
      <section className="ingreso-formulario">
        <div className="ingreso-marca"><LogoEstiba tamano={44} />Estiba</div>
        <div>
          <h1>Ingresar</h1>
          <p className="ingreso-intro">Inventario por bodega, compras y devoluciones del supermercado.</p>
        </div>

        <form className="formulario" onSubmit={enviar} noValidate>
          {error && !Object.keys(campos).length && <ErrorCaja error={error} />}
          <Campo id="email" etiqueta="Correo" error={campos.email}>
            <input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} aria-describedby={campos.email ? 'email-error' : undefined} />
          </Campo>
          <Campo id="password" etiqueta="Contraseña" error={campos.password}>
            <input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Campo>
          <div className="acciones-separadas">
            <BotonEnvio enviando={enviando}>Ingresar</BotonEnvio>
            <Link to="/recuperar">¿Olvidaste tu contraseña?</Link>
          </div>
        </form>

        <div className="ingreso-demo">
          <p>Plantilla con datos de ejemplo: elige un usuario para ver la interfaz de su rol. Cualquier contraseña sirve.</p>
          <div>
            {usuarios.map((u) => (
              <button key={u.id} type="button" className="btn btn-sm" onClick={() => { setEmail(u.email); setPassword('demo1234') }}>
                {u.nombre.split(' ')[0]} · {nombreRol[u.rol]}{u.estado === 'INACTIVO' ? ' (inactivo)' : ''}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="ingreso-escena" aria-hidden="true">
        <RackBodega saldos={saldosPortada} codigoBodega="B1" nombreBodega="Bodega Principal" seleccionado={null} onSeleccionar={() => {}} alto="100%" interactivo={false} />
        <p className="ingreso-lema">Cada unidad que entra, sale o cambia de bodega queda firmada en el kardex.</p>
      </section>
    </div>
  )
}

export function Recuperar() {
  const [email, setEmail] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [listo, setListo] = useState(false)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setEnviando(true)
    await auth.recuperar(email)
    setEnviando(false)
    setListo(true)
  }

  return (
    <div className="ingreso">
      <section className="ingreso-formulario">
        <div className="ingreso-marca"><LogoEstiba tamano={44} />Estiba</div>
        <div>
          <h1>Recuperar contraseña</h1>
          <p className="ingreso-intro">Escribe tu correo y te enviaremos un enlace para crear una contraseña nueva.</p>
        </div>
        {listo ? (
          <div className="aviso aviso-info" role="status">
            <div>
              <strong>Revisa tu correo</strong>
              <p>Si {email} está registrado, recibirás el enlace en unos minutos. El enlace vence en una hora.</p>
            </div>
          </div>
        ) : (
          <form className="formulario" onSubmit={enviar}>
            <Campo id="email-recuperar" etiqueta="Correo">
              <input id="email-recuperar" type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
            </Campo>
            <div className="acciones-separadas">
              <BotonEnvio enviando={enviando}>Enviar enlace</BotonEnvio>
            </div>
          </form>
        )}
        <Link to="/ingresar">Volver a ingresar</Link>
      </section>
      <section className="ingreso-escena" aria-hidden="true">
        <p className="ingreso-lema">El enlace llega al correo registrado; por seguridad no confirmamos si un correo existe.</p>
      </section>
    </div>
  )
}
