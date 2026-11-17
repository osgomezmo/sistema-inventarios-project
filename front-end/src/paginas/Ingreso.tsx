import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { Clock } from 'lucide-react'
import { auth } from '../api/cliente'
import { useSesion } from '../auth/Sesion'
import { LogoEstiba } from '../componentes/Marca'
import { BotonEnvio, Campo, ErrorCaja, erroresCampo } from '../componentes/ui'
import { RackBodega } from '../tres/RackDiferido'
import { categoriaPortada, saldosPortada } from '../tres/portada'
import { reglas, useValidacion, validar } from '../lib/validacion'

export function Ingreso() {
  const { sesion, expirada, iniciar } = useSesion()
  const navegar = useNavigate()
  const ubicacion = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const v = useValidacion(validar({
    email: [reglas.requerido(email, 'Escribe tu correo.'), reglas.email(email)],
    password: [reglas.requerido(password, 'Escribe tu contraseña.')],
  }))

  if (sesion) return <Navigate to="/" replace />
  const destino = (ubicacion.state as { desde?: string } | null)?.desde ?? '/'
  const campos = { ...erroresCampo(error), ...v.visibles }

  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!v.comprobar(e.currentTarget)) return
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

        <form className="formulario" onSubmit={enviar} onBlur={v.alSalir} noValidate>
          {expirada && !error && (
            <div className="aviso aviso-info" role="status">
              <Clock size={22} aria-hidden />
              <div><strong>Tu sesión terminó</strong><p>El token venció o fue revocado. Ingresa de nuevo para seguir.</p></div>
            </div>
          )}
          {error && !Object.keys(erroresCampo(error)).length && <ErrorCaja error={error} />}
          <Campo id="email" etiqueta="Correo" error={campos.email}>
            <input id="email" name="email" type="email" autoComplete="username" maxLength={120} value={email} onChange={(e) => setEmail(e.target.value)} />
          </Campo>
          <Campo id="password" etiqueta="Contraseña" error={campos.password}>
            <input id="password" name="password" type="password" autoComplete="current-password" maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} />
          </Campo>
          <div className="acciones-separadas">
            <BotonEnvio enviando={enviando}>Ingresar</BotonEnvio>
            <Link to="/recuperar">¿Olvidaste tu contraseña?</Link>
          </div>
        </form>
      </section>

      <section className="ingreso-escena" aria-hidden="true">
        <RackBodega saldos={saldosPortada} categoriaDe={categoriaPortada} codigoBodega="B1" nombreBodega="Bodega" seleccionado={null} onSeleccionar={() => {}} alto="100%" interactivo={false} />
        <p className="ingreso-lema">Cada unidad que entra, sale o cambia de bodega queda firmada en el kardex.</p>
      </section>
    </div>
  )
}

/**
 * El gateway no expone un endpoint de recuperación por correo: la contraseña la
 * cambia la propia persona desde su perfil, o el administrador crea un usuario nuevo.
 */
export function Recuperar() {
  return (
    <div className="ingreso">
      <section className="ingreso-formulario">
        <div className="ingreso-marca"><LogoEstiba tamano={44} />Estiba</div>
        <div>
          <h1>¿Olvidaste tu contraseña?</h1>
          <p className="ingreso-intro">Pídele al administrador del sistema que revise tu usuario. Si recuerdas la contraseña actual, puedes cambiarla después de ingresar, desde el menú de tu nombre.</p>
        </div>
        <Link className="btn btn-pri" to="/ingresar">Volver a ingresar</Link>
      </section>
      <section className="ingreso-escena" aria-hidden="true">
        <p className="ingreso-lema">Las contraseñas y los tokens de acceso viven en el API Gateway; ningún microservicio los conoce.</p>
      </section>
    </div>
  )
}
