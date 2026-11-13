// Formularios de alta de los maestros. Se abren en línea sobre su tabla (sin modal):
// la persona sigue viendo el listado al que agrega el registro. Cada uno valida en el
// cliente antes de enviar; el servicio vuelve a validar (422 y 409 por duplicados).
import { useState, type FocusEvent, type FormEvent, type ReactNode } from 'react'
import type { UnidadMedida } from '../api/types'
import { altasApi } from '../api/cliente'
import { categorias, roles } from '../api/mock/maestros'
import { nombreRol } from '../auth/permisos'
import { BotonEnvio, Campo, ErrorCaja, erroresCampo } from '../componentes/ui'
import { aNumero, decimalesPorUnidad, reglas, useValidacion, validar, type Errores } from '../lib/validacion'

interface PropsAlta { listo: (texto: string) => void; cancelar: () => void }

/** Envío con validación: primero el cliente, luego el servicio. campos mezcla los dos. */
function useEnvio(errores: Errores) {
  const v = useValidacion(errores)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  async function ejecutar(e: FormEvent<HTMLFormElement>, accion: () => Promise<void>) {
    e.preventDefault()
    if (!v.comprobar(e.currentTarget)) return
    setEnviando(true)
    setError(null)
    try { await accion() } catch (err) { setError(err as Error) } finally { setEnviando(false) }
  }
  return { enviando, error, campos: { ...erroresCampo(error), ...v.visibles }, ejecutar, alSalir: v.alSalir }
}

function Marco({ titulo, error, enviando, cancelar, onSubmit, alSalir, boton, children }: {
  titulo: string; error: Error | null; enviando: boolean; cancelar: () => void
  onSubmit: (e: FormEvent<HTMLFormElement>) => void; alSalir: (e: FocusEvent<HTMLElement>) => void; boton: string; children: ReactNode
}) {
  return (
    <form className="panel formulario" style={{ maxWidth: 'none', marginBottom: 20 }} onSubmit={onSubmit} onBlur={alSalir} noValidate>
      <h2>{titulo}</h2>
      {error && !Object.keys(erroresCampo(error)).length && <ErrorCaja error={error} />}
      {children}
      <div className="acciones-separadas">
        <BotonEnvio enviando={enviando}>{boton}</BotonEnvio>
        <button type="button" className="btn btn-fantasma" onClick={cancelar}>Cancelar</button>
      </div>
    </form>
  )
}

const largoRequerido = (v: string, min: number, max: number, mensaje: string) => [reglas.requerido(v, mensaje), reglas.largo(v, min, max)]

export function AltaProducto({ listo, cancelar }: PropsAlta) {
  const [v, setV] = useState({ sku: '', nombre: '', marca: '', descripcion: '', id_categoria: '', unidad_medida: 'UNIDAD', precio_venta: '', stock_minimo: '' })
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value })
  const unidad = v.unidad_medida as UnidadMedida
  const { enviando, error, campos, ejecutar, alSalir } = useEnvio(validar({
    sku: [reglas.requerido(v.sku, 'Escribe el SKU.'), reglas.sku(v.sku)],
    nombre: largoRequerido(v.nombre, 3, 80, 'Escribe el nombre del producto.'),
    marca: largoRequerido(v.marca, 2, 40, 'Escribe la marca.'),
    id_categoria: [reglas.requerido(v.id_categoria, 'Elige la subcategoría.')],
    precio_venta: [reglas.numero(v.precio_venta, { requerido: true, mensajeVacio: 'Escribe el precio de venta.', decimales: 2, mayorQueCero: true, max: 100_000_000, mensajeMax: 'Revisa el precio: supera $ 100.000.000.' })],
    stock_minimo: [reglas.numero(v.stock_minimo, { requerido: true, mensajeVacio: 'Escribe el stock mínimo por bodega.', decimales: decimalesPorUnidad(unidad), min: 0 })],
    descripcion: [reglas.largo(v.descripcion, 0, 200)],
  }))
  const hojas = categorias.filter((c) => c.id_categoria_padre !== null && c.estado === 'ACTIVO')
  return (
    <Marco titulo="Nuevo producto" error={error} enviando={enviando} cancelar={cancelar} alSalir={alSalir} boton="Crear producto"
      onSubmit={(e) => ejecutar(e, async () => {
        const p = await altasApi.producto({ sku: v.sku.trim().toUpperCase(), nombre: v.nombre.trim(), marca: v.marca.trim(), descripcion: v.descripcion.trim(), id_categoria: Number(v.id_categoria), unidad_medida: unidad, precio_venta: aNumero(v.precio_venta) ?? 0, stock_minimo: aNumero(v.stock_minimo) ?? 0 })
        listo(`${p.sku} creado`)
      })}>
      <div className="fila-campos">
        <Campo id="ap-sku" etiqueta="SKU" error={campos.sku} ayuda="Único. Por ejemplo LAC-0210."><input id="ap-sku" name="sku" maxLength={8} value={v.sku} onChange={set('sku')} /></Campo>
        <Campo id="ap-nombre" etiqueta="Nombre" error={campos.nombre}><input id="ap-nombre" name="nombre" maxLength={80} value={v.nombre} onChange={set('nombre')} /></Campo>
        <Campo id="ap-marca" etiqueta="Marca" error={campos.marca}><input id="ap-marca" name="marca" maxLength={40} value={v.marca} onChange={set('marca')} /></Campo>
      </div>
      <div className="fila-campos">
        <Campo id="ap-cat" etiqueta="Categoría" error={campos.id_categoria}>
          <select id="ap-cat" name="id_categoria" value={v.id_categoria} onChange={set('id_categoria')}>
            <option value="">Elige una subcategoría</option>
            {hojas.map((c) => <option key={c.id_categoria} value={c.id_categoria}>{categorias.find((x) => x.id_categoria === c.id_categoria_padre)!.nombre} › {c.nombre}</option>)}
          </select>
        </Campo>
        <Campo id="ap-unidad" etiqueta="Unidad de medida">
          <select id="ap-unidad" name="unidad_medida" value={v.unidad_medida} onChange={set('unidad_medida')}><option value="UNIDAD">Unidad</option><option value="KILO">Kilo</option><option value="LITRO">Litro</option></select>
        </Campo>
        <Campo id="ap-precio" etiqueta="Precio de venta" error={campos.precio_venta}><input id="ap-precio" name="precio_venta" inputMode="decimal" maxLength={14} value={v.precio_venta} onChange={set('precio_venta')} /></Campo>
        <Campo id="ap-min" etiqueta="Stock mínimo por bodega" error={campos.stock_minimo} ayuda={unidad === 'UNIDAD' ? 'En unidades enteras.' : 'Hasta tres decimales.'}><input id="ap-min" name="stock_minimo" inputMode="decimal" maxLength={14} value={v.stock_minimo} onChange={set('stock_minimo')} /></Campo>
      </div>
      <Campo id="ap-desc" etiqueta="Descripción" opcional error={campos.descripcion}><textarea id="ap-desc" name="descripcion" maxLength={200} value={v.descripcion} onChange={set('descripcion')} /></Campo>
    </Marco>
  )
}

export function AltaCategoria({ listo, cancelar }: PropsAlta) {
  const [nombre, setNombre] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [padre, setPadre] = useState('')
  const { enviando, error, campos, ejecutar, alSalir } = useEnvio(validar({
    nombre: largoRequerido(nombre, 3, 40, 'Escribe el nombre de la categoría.'),
    descripcion: [reglas.largo(descripcion, 0, 200)],
  }))
  return (
    <Marco titulo="Nueva categoría" error={error} enviando={enviando} cancelar={cancelar} alSalir={alSalir} boton="Crear categoría"
      onSubmit={(e) => ejecutar(e, async () => { const c = await altasApi.categoria({ nombre: nombre.trim(), descripcion: descripcion.trim(), id_categoria_padre: padre ? Number(padre) : null }); listo(`Categoría ${c.nombre} creada`) })}>
      <div className="fila-campos">
        <Campo id="ac-nombre" etiqueta="Nombre" error={campos.nombre}><input id="ac-nombre" name="nombre" maxLength={40} value={nombre} onChange={(e) => setNombre(e.target.value)} /></Campo>
        <Campo id="ac-padre" etiqueta="Dentro de" opcional>
          <select id="ac-padre" name="id_categoria_padre" value={padre} onChange={(e) => setPadre(e.target.value)}>
            <option value="">Ninguna (categoría principal)</option>
            {categorias.filter((c) => c.id_categoria_padre === null && c.estado === 'ACTIVO').map((c) => <option key={c.id_categoria} value={c.id_categoria}>{c.nombre}</option>)}
          </select>
        </Campo>
      </div>
      <Campo id="ac-desc" etiqueta="Descripción" opcional error={campos.descripcion}><textarea id="ac-desc" name="descripcion" maxLength={200} value={descripcion} onChange={(e) => setDescripcion(e.target.value)} /></Campo>
    </Marco>
  )
}

export function AltaProveedor({ listo, cancelar }: PropsAlta) {
  const [v, setV] = useState({ nit: '', razon_social: '', telefono: '', email: '', direccion: '' })
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value })
  const { enviando, error, campos, ejecutar, alSalir } = useEnvio(validar({
    nit: [reglas.requerido(v.nit, 'Escribe el NIT.'), reglas.nit(v.nit)],
    razon_social: largoRequerido(v.razon_social, 3, 100, 'Escribe la razón social.'),
    telefono: [reglas.requerido(v.telefono, 'Escribe un teléfono de contacto.'), reglas.telefono(v.telefono)],
    email: [reglas.requerido(v.email, 'Escribe el correo de pedidos.'), reglas.email(v.email)],
    direccion: largoRequerido(v.direccion, 5, 120, 'Escribe la dirección.'),
  }))
  return (
    <Marco titulo="Nuevo proveedor" error={error} enviando={enviando} cancelar={cancelar} alSalir={alSalir} boton="Crear proveedor"
      onSubmit={(e) => ejecutar(e, async () => {
        const p = await altasApi.proveedor({ nit: v.nit.trim(), razon_social: v.razon_social.trim(), telefono: v.telefono.trim(), email: v.email.trim().toLowerCase(), direccion: v.direccion.trim() })
        listo(`${p.razon_social} creado`)
      })}>
      <div className="fila-campos">
        <Campo id="pv-nit" etiqueta="NIT" error={campos.nit} ayuda="Con dígito de verificación: 900.123.456-7"><input id="pv-nit" name="nit" maxLength={16} value={v.nit} onChange={set('nit')} /></Campo>
        <Campo id="pv-razon" etiqueta="Razón social" error={campos.razon_social}><input id="pv-razon" name="razon_social" maxLength={100} value={v.razon_social} onChange={set('razon_social')} /></Campo>
      </div>
      <div className="fila-campos">
        <Campo id="pv-tel" etiqueta="Teléfono" error={campos.telefono}><input id="pv-tel" name="telefono" type="tel" maxLength={20} value={v.telefono} onChange={set('telefono')} /></Campo>
        <Campo id="pv-email" etiqueta="Correo" error={campos.email}><input id="pv-email" name="email" type="email" maxLength={120} value={v.email} onChange={set('email')} /></Campo>
        <Campo id="pv-dir" etiqueta="Dirección" error={campos.direccion}><input id="pv-dir" name="direccion" maxLength={120} value={v.direccion} onChange={set('direccion')} /></Campo>
      </div>
    </Marco>
  )
}

export function AltaBodega({ listo, cancelar }: PropsAlta) {
  const [v, setV] = useState({ codigo: '', nombre: '', direccion: '' })
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value })
  const { enviando, error, campos, ejecutar, alSalir } = useEnvio(validar({
    codigo: [reglas.requerido(v.codigo, 'Escribe el código de la bodega.'), reglas.codigoBodega(v.codigo)],
    nombre: largoRequerido(v.nombre, 3, 60, 'Escribe el nombre de la bodega.'),
    direccion: largoRequerido(v.direccion, 5, 120, 'Escribe la dirección.'),
  }))
  return (
    <Marco titulo="Nueva bodega" error={error} enviando={enviando} cancelar={cancelar} alSalir={alSalir} boton="Crear bodega"
      onSubmit={(e) => ejecutar(e, async () => { const b = await altasApi.bodega({ codigo: v.codigo.trim().toUpperCase(), nombre: v.nombre.trim(), direccion: v.direccion.trim() }); listo(`Bodega ${b.codigo} creada`) })}>
      <div className="fila-campos">
        <Campo id="ab-cod" etiqueta="Código" error={campos.codigo} ayuda="Una letra y hasta tres números, por ejemplo B5."><input id="ab-cod" name="codigo" maxLength={4} value={v.codigo} onChange={set('codigo')} /></Campo>
        <Campo id="ab-nombre" etiqueta="Nombre" error={campos.nombre}><input id="ab-nombre" name="nombre" maxLength={60} value={v.nombre} onChange={set('nombre')} /></Campo>
        <Campo id="ab-dir" etiqueta="Dirección" error={campos.direccion}><input id="ab-dir" name="direccion" maxLength={120} value={v.direccion} onChange={set('direccion')} /></Campo>
      </div>
    </Marco>
  )
}

export function AltaUsuario({ listo, cancelar }: PropsAlta) {
  const [v, setV] = useState({ nombre: '', email: '', password: '', id_rol: '2' })
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value })
  const { enviando, error, campos, ejecutar, alSalir } = useEnvio(validar({
    nombre: [...largoRequerido(v.nombre, 3, 80, 'Escribe el nombre completo.'), reglas.nombrePersona(v.nombre)],
    email: [reglas.requerido(v.email, 'Escribe el correo.'), reglas.email(v.email)],
    password: [reglas.requerido(v.password, 'Escribe una contraseña inicial.'), reglas.password(v.password)],
    id_rol: [reglas.requerido(v.id_rol, 'Elige un rol.')],
  }))
  return (
    <Marco titulo="Nuevo usuario" error={error} enviando={enviando} cancelar={cancelar} alSalir={alSalir} boton="Crear usuario"
      onSubmit={(e) => ejecutar(e, async () => { const u = await altasApi.usuario({ nombre: v.nombre.trim(), email: v.email.trim().toLowerCase(), password: v.password, id_rol: Number(v.id_rol) }); listo(`${u.nombre} creado como ${nombreRol[u.rol].toLowerCase()}`) })}>
      <div className="fila-campos">
        <Campo id="au-nombre" etiqueta="Nombre completo" error={campos.nombre}><input id="au-nombre" name="nombre" maxLength={80} autoComplete="off" value={v.nombre} onChange={set('nombre')} /></Campo>
        <Campo id="au-email" etiqueta="Correo" error={campos.email}><input id="au-email" name="email" type="email" maxLength={120} autoComplete="off" value={v.email} onChange={set('email')} /></Campo>
      </div>
      <div className="fila-campos">
        <Campo id="au-pw" etiqueta="Contraseña inicial" error={campos.password} ayuda="Mínimo 8 caracteres, con letras y números; la persona la cambia al ingresar."><input id="au-pw" name="password" type="password" autoComplete="new-password" maxLength={128} value={v.password} onChange={set('password')} /></Campo>
        <Campo id="au-rol" etiqueta="Rol" error={campos.id_rol}>
          <select id="au-rol" name="id_rol" value={v.id_rol} onChange={set('id_rol')}>{roles.map((r) => <option key={r.id_rol} value={r.id_rol}>{nombreRol[r.nombre]}</option>)}</select>
        </Campo>
      </div>
    </Marco>
  )
}
