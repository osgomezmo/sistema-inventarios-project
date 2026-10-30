// Formularios de alta de los maestros. Se abren en línea sobre su tabla (sin modal):
// la persona sigue viendo el listado al que agrega el registro.
import { useState, type FormEvent, type ReactNode } from 'react'
import type { UnidadMedida } from '../api/types'
import { altasApi } from '../api/cliente'
import { categorias, roles } from '../api/mock/maestros'
import { nombreRol } from '../auth/permisos'
import { BotonEnvio, Campo, ErrorCaja, erroresCampo } from '../componentes/ui'

interface PropsAlta { listo: (texto: string) => void; cancelar: () => void }

function useEnvio() {
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  async function ejecutar(e: FormEvent, accion: () => Promise<void>) {
    e.preventDefault()
    setEnviando(true)
    setError(null)
    try { await accion() } catch (err) { setError(err as Error) } finally { setEnviando(false) }
  }
  return { enviando, error, campos: erroresCampo(error), ejecutar }
}

function Marco({ titulo, error, campos, enviando, cancelar, onSubmit, boton, children }: {
  titulo: string; error: Error | null; campos: Record<string, string[]>; enviando: boolean; cancelar: () => void
  onSubmit: (e: FormEvent) => void; boton: string; children: ReactNode
}) {
  return (
    <form className="panel formulario" style={{ maxWidth: 'none', marginBottom: 20 }} onSubmit={onSubmit} noValidate>
      <h2>{titulo}</h2>
      {error && !Object.keys(campos).length && <ErrorCaja error={error} />}
      {children}
      <div className="acciones-separadas">
        <BotonEnvio enviando={enviando}>{boton}</BotonEnvio>
        <button type="button" className="btn btn-fantasma" onClick={cancelar}>Cancelar</button>
      </div>
    </form>
  )
}

export function AltaProducto({ listo, cancelar }: PropsAlta) {
  const { enviando, error, campos, ejecutar } = useEnvio()
  const [v, setV] = useState({ sku: '', nombre: '', marca: '', descripcion: '', id_categoria: '', unidad_medida: 'UNIDAD', precio_venta: '', stock_minimo: '' })
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value })
  const hojas = categorias.filter((c) => c.id_categoria_padre !== null && c.estado === 'ACTIVO')
  return (
    <Marco titulo="Nuevo producto" error={error} campos={campos} enviando={enviando} cancelar={cancelar} boton="Crear producto"
      onSubmit={(e) => ejecutar(e, async () => {
        const p = await altasApi.producto({ sku: v.sku, nombre: v.nombre, marca: v.marca, descripcion: v.descripcion, id_categoria: Number(v.id_categoria) || (undefined as unknown as number), unidad_medida: v.unidad_medida as UnidadMedida, precio_venta: v.precio_venta === '' ? NaN : Number(v.precio_venta), stock_minimo: v.stock_minimo === '' ? NaN : Number(v.stock_minimo) })
        listo(`${p.sku} creado`)
      })}>
      <div className="fila-campos">
        <Campo id="ap-sku" etiqueta="SKU" error={campos.sku} ayuda="Único. Por ejemplo LAC-0210."><input id="ap-sku" value={v.sku} onChange={set('sku')} /></Campo>
        <Campo id="ap-nombre" etiqueta="Nombre" error={campos.nombre}><input id="ap-nombre" value={v.nombre} onChange={set('nombre')} /></Campo>
        <Campo id="ap-marca" etiqueta="Marca" error={campos.marca}><input id="ap-marca" value={v.marca} onChange={set('marca')} /></Campo>
      </div>
      <div className="fila-campos">
        <Campo id="ap-cat" etiqueta="Categoría" error={campos.id_categoria}>
          <select id="ap-cat" value={v.id_categoria} onChange={set('id_categoria')}>
            <option value="">Elige una subcategoría</option>
            {hojas.map((c) => <option key={c.id_categoria} value={c.id_categoria}>{categorias.find((x) => x.id_categoria === c.id_categoria_padre)!.nombre} › {c.nombre}</option>)}
          </select>
        </Campo>
        <Campo id="ap-unidad" etiqueta="Unidad de medida">
          <select id="ap-unidad" value={v.unidad_medida} onChange={set('unidad_medida')}><option value="UNIDAD">Unidad</option><option value="KILO">Kilo</option><option value="LITRO">Litro</option></select>
        </Campo>
        <Campo id="ap-precio" etiqueta="Precio de venta" error={campos.precio_venta}><input id="ap-precio" inputMode="numeric" value={v.precio_venta} onChange={set('precio_venta')} /></Campo>
        <Campo id="ap-min" etiqueta="Stock mínimo por bodega" error={campos.stock_minimo}><input id="ap-min" inputMode="decimal" value={v.stock_minimo} onChange={set('stock_minimo')} /></Campo>
      </div>
      <Campo id="ap-desc" etiqueta="Descripción" opcional><textarea id="ap-desc" value={v.descripcion} onChange={set('descripcion')} /></Campo>
    </Marco>
  )
}

export function AltaCategoria({ listo, cancelar }: PropsAlta) {
  const { enviando, error, campos, ejecutar } = useEnvio()
  const [nombre, setNombre] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [padre, setPadre] = useState('')
  return (
    <Marco titulo="Nueva categoría" error={error} campos={campos} enviando={enviando} cancelar={cancelar} boton="Crear categoría"
      onSubmit={(e) => ejecutar(e, async () => { const c = await altasApi.categoria({ nombre, descripcion, id_categoria_padre: padre ? Number(padre) : null }); listo(`Categoría ${c.nombre} creada`) })}>
      <div className="fila-campos">
        <Campo id="ac-nombre" etiqueta="Nombre" error={campos.nombre}><input id="ac-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} /></Campo>
        <Campo id="ac-padre" etiqueta="Dentro de" opcional>
          <select id="ac-padre" value={padre} onChange={(e) => setPadre(e.target.value)}>
            <option value="">Ninguna (categoría principal)</option>
            {categorias.filter((c) => c.id_categoria_padre === null && c.estado === 'ACTIVO').map((c) => <option key={c.id_categoria} value={c.id_categoria}>{c.nombre}</option>)}
          </select>
        </Campo>
      </div>
      <Campo id="ac-desc" etiqueta="Descripción" opcional><textarea id="ac-desc" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} /></Campo>
    </Marco>
  )
}

export function AltaProveedor({ listo, cancelar }: PropsAlta) {
  const { enviando, error, campos, ejecutar } = useEnvio()
  const [v, setV] = useState({ nit: '', razon_social: '', telefono: '', email: '', direccion: '' })
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value })
  return (
    <Marco titulo="Nuevo proveedor" error={error} campos={campos} enviando={enviando} cancelar={cancelar} boton="Crear proveedor"
      onSubmit={(e) => ejecutar(e, async () => { const p = await altasApi.proveedor(v); listo(`${p.razon_social} creado`) })}>
      <div className="fila-campos">
        <Campo id="pv-nit" etiqueta="NIT" error={campos.nit} ayuda="Con dígito de verificación: 900.123.456-7"><input id="pv-nit" value={v.nit} onChange={set('nit')} /></Campo>
        <Campo id="pv-razon" etiqueta="Razón social" error={campos.razon_social}><input id="pv-razon" value={v.razon_social} onChange={set('razon_social')} /></Campo>
      </div>
      <div className="fila-campos">
        <Campo id="pv-tel" etiqueta="Teléfono" error={campos.telefono}><input id="pv-tel" type="tel" value={v.telefono} onChange={set('telefono')} /></Campo>
        <Campo id="pv-email" etiqueta="Correo" error={campos.email}><input id="pv-email" type="email" value={v.email} onChange={set('email')} /></Campo>
        <Campo id="pv-dir" etiqueta="Dirección" error={campos.direccion}><input id="pv-dir" value={v.direccion} onChange={set('direccion')} /></Campo>
      </div>
    </Marco>
  )
}

export function AltaBodega({ listo, cancelar }: PropsAlta) {
  const { enviando, error, campos, ejecutar } = useEnvio()
  const [v, setV] = useState({ codigo: '', nombre: '', direccion: '' })
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value })
  return (
    <Marco titulo="Nueva bodega" error={error} campos={campos} enviando={enviando} cancelar={cancelar} boton="Crear bodega"
      onSubmit={(e) => ejecutar(e, async () => { const b = await altasApi.bodega(v); listo(`Bodega ${b.codigo} creada`) })}>
      <div className="fila-campos">
        <Campo id="ab-cod" etiqueta="Código" error={campos.codigo} ayuda="Corto y único, por ejemplo B5."><input id="ab-cod" value={v.codigo} onChange={set('codigo')} /></Campo>
        <Campo id="ab-nombre" etiqueta="Nombre" error={campos.nombre}><input id="ab-nombre" value={v.nombre} onChange={set('nombre')} /></Campo>
        <Campo id="ab-dir" etiqueta="Dirección" error={campos.direccion}><input id="ab-dir" value={v.direccion} onChange={set('direccion')} /></Campo>
      </div>
    </Marco>
  )
}

export function AltaUsuario({ listo, cancelar }: PropsAlta) {
  const { enviando, error, campos, ejecutar } = useEnvio()
  const [v, setV] = useState({ nombre: '', email: '', password: '', id_rol: '2' })
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value })
  return (
    <Marco titulo="Nuevo usuario" error={error} campos={campos} enviando={enviando} cancelar={cancelar} boton="Crear usuario"
      onSubmit={(e) => ejecutar(e, async () => { const u = await altasApi.usuario({ ...v, id_rol: Number(v.id_rol) }); listo(`${u.nombre} creado como ${nombreRol[u.rol].toLowerCase()}`) })}>
      <div className="fila-campos">
        <Campo id="au-nombre" etiqueta="Nombre completo" error={campos.nombre}><input id="au-nombre" value={v.nombre} onChange={set('nombre')} /></Campo>
        <Campo id="au-email" etiqueta="Correo" error={campos.email}><input id="au-email" type="email" value={v.email} onChange={set('email')} /></Campo>
      </div>
      <div className="fila-campos">
        <Campo id="au-pw" etiqueta="Contraseña inicial" error={campos.password} ayuda="Mínimo 8 caracteres; la persona la cambia al ingresar."><input id="au-pw" type="password" autoComplete="new-password" value={v.password} onChange={set('password')} /></Campo>
        <Campo id="au-rol" etiqueta="Rol">
          <select id="au-rol" value={v.id_rol} onChange={set('id_rol')}>{roles.map((r) => <option key={r.id_rol} value={r.id_rol}>{nombreRol[r.nombre]}</option>)}</select>
        </Campo>
      </div>
    </Marco>
  )
}
