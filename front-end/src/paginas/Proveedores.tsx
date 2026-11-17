import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import { Mail, Pencil, Phone, Plus, Trash2 } from 'lucide-react'
import type { Estado, ProductoSuministrado } from '../api/types'
import { ordenesApi, proveedoresApi } from '../api/cliente'
import { producto, productos } from '../api/maestros'
import { useUsuario } from '../auth/Sesion'
import { puedeEditar, puedeVer } from '../auth/permisos'
import { BotonEnvio, Campo, Cargando, Encabezado, ErrorCaja, EtiquetaEstado, EtiquetaOrden, Paginacion, Vacio, erroresCampo } from '../componentes/ui'
import { dinero, fecha } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'
import { aNumero, reglas, useValidacion, validar } from '../lib/validacion'
import { useAvisos } from '../contexto/Avisos'
import { useMaestros } from '../contexto/Maestros'
import { AltaProveedor } from './Altas'

export function Proveedores() {
  const usuario = useUsuario()
  const avisar = useAvisos()
  const { recargar } = useMaestros()
  const [alta, setAlta] = useState(false)
  const [q, setQ] = useState('')
  const [estado, setEstado] = useState<'' | 'ACTIVO' | 'INACTIVO'>('')
  const [page, setPage] = useState(1)
  const c = useConsulta(() => proveedoresApi.listar({ q: q.trim(), estado: estado || undefined, page }), [q, estado, page])
  return (
    <>
      <Encabezado
        titulo="Proveedores"
        descripcion="Un proveedor inactivo no puede usarse en órdenes nuevas."
        acciones={puedeEditar(usuario.rol, 'proveedores') && <button type="button" className="btn btn-pri" aria-expanded={alta} onClick={() => setAlta(!alta)}><Plus size={18} aria-hidden />Nuevo proveedor</button>}
      />
      {alta && <AltaProveedor listo={(t) => { avisar(t); setAlta(false); c.recargar(); recargar().catch(() => {}) }} cancelar={() => setAlta(false)} />}
      <div className="filtros">
        <div className="campo ancho"><label htmlFor="p-q">Buscar</label><input id="p-q" type="search" placeholder="NIT o razón social" maxLength={60} value={q} onChange={(e) => { setQ(e.target.value); setPage(1) }} /></div>
        <div className="campo">
          <label htmlFor="p-estado">Estado</label>
          <select id="p-estado" value={estado} onChange={(e) => { setEstado(e.target.value as typeof estado); setPage(1) }}>
            <option value="">Todos</option><option value="ACTIVO">Activos</option><option value="INACTIVO">Inactivos</option>
          </select>
        </div>
      </div>
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      <div className="tabla-envoltura">
        {!c.datos && !c.error && <Cargando />}
        {c.datos && (c.datos.data.length === 0 ? <Vacio titulo="Ningún proveedor coincide">Prueba con otra parte del NIT o del nombre.</Vacio> : (
          <>
          <table className="tabla">
            <thead><tr><th>Proveedor</th><th>NIT</th><th>Contacto principal</th><th>Teléfono</th><th>Estado</th></tr></thead>
            <tbody>
              {c.datos.data.map((p) => (
                <tr key={p.id_proveedor}>
                  <td><Link to={`/proveedores/${p.id_proveedor}`}><strong>{p.razon_social}</strong></Link><span className="secundario">{p.direccion}</span></td>
                  <td className="cifra">{p.nit}</td>
                  <td>{p.contactos[0]?.nombre ?? '—'}<span className="secundario">{p.contactos[0]?.cargo}</span></td>
                  <td className="cifra">{p.telefono}</td>
                  <td><EtiquetaEstado estado={p.estado} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <Paginacion meta={c.datos.meta} cambiar={setPage} />
          </>
        ))}
      </div>
    </>
  )
}

export function ProveedorDetalle() {
  const { id = '' } = useParams()
  const usuario = useUsuario()
  const avisar = useAvisos()
  const { recargar } = useMaestros()
  const verOrdenes = puedeVer(usuario.rol, 'ordenes')
  const edita = puedeEditar(usuario.rol, 'proveedores')
  // Las órdenes vienen de ms-compras: si no responde, el resto del proveedor se muestra igual.
  const c = useConsulta(() => Promise.all([
    proveedoresApi.obtener(Number(id)),
    proveedoresApi.productos(Number(id)),
    verOrdenes ? ordenesApi.listar({ id_proveedor: Number(id), per_page: 20 }).catch(() => null) : Promise.resolve(null),
  ]), [id, verOrdenes])
  /** Formulario de producto abierto: sin inicial asocia uno nuevo; con inicial edita ese renglón. */
  const [formProducto, setFormProducto] = useState<{ inicial?: ProductoSuministrado } | null>(null)
  const [formContacto, setFormContacto] = useState(false)
  /** Elemento que espera confirmación para quitarse: «p:SKU» o «c:ID». */
  const [confirmar, setConfirmar] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState<string | null>(null)
  const [accionError, setAccionError] = useState<Error | null>(null)

  if (c.error) return <ErrorCaja error={c.error} reintentar={c.recargar} />
  if (!c.datos) return <div className="panel"><Cargando /></div>
  const [p, suministra, ordenes] = c.datos

  /** Ejecuta una acción de una fila, avisa y vuelve a leer la ficha. */
  async function accion(clave: string, ejecutar: () => Promise<unknown>, texto: string, conMaestros = false) {
    setOcupado(clave)
    setAccionError(null)
    try {
      await ejecutar()
      avisar(texto)
      setConfirmar(null)
      c.recargar()
      if (conMaestros) recargar().catch(() => {})
    } catch (e) {
      setAccionError(e as Error)
    } finally {
      setOcupado(null)
    }
  }

  const cambiarEstado = (nuevo: Estado) => accion(
    'estado',
    () => proveedoresApi.cambiarEstado(p.id_proveedor, nuevo),
    nuevo === 'ACTIVO' ? `${p.razon_social} quedó activo` : `${p.razon_social} quedó inactivo: no se podrá usar en órdenes nuevas`,
    true,
  )

  const listoFormulario = (texto: string) => { avisar(texto); setFormProducto(null); setFormContacto(false); c.recargar() }

  return (
    <>
      <Encabezado
        migas={<><Link to="/proveedores">Proveedores</Link><span aria-hidden>/</span><span>{p.nit}</span></>}
        titulo={p.razon_social}
        descripcion={<>NIT {p.nit} · {p.direccion}</>}
        acciones={
          <>
            <EtiquetaEstado estado={p.estado} />
            {edita && (p.estado === 'ACTIVO'
              ? <button type="button" className="btn" disabled={!!ocupado} onClick={() => cambiarEstado('INACTIVO')}>Inactivar proveedor</button>
              : <button type="button" className="btn btn-pri" disabled={!!ocupado} onClick={() => cambiarEstado('ACTIVO')}>Activar proveedor</button>)}
          </>
        }
      />
      {accionError && <ErrorCaja error={accionError} />}
      <div className="dos-columnas">
        <div className="pila">
          <section className="tabla-envoltura" aria-labelledby="t-sum">
            <div className="panel-titulo" style={{ padding: '16px 16px 0' }}>
              <h2 id="t-sum">Productos que suministra</h2>
              {edita && !formProducto && <button type="button" className="btn btn-sm" onClick={() => { setFormProducto({}); setConfirmar(null) }}><Plus size={16} aria-hidden />Asociar producto</button>}
            </div>
            {formProducto && (
              <FormSuministro key={formProducto.inicial?.sku ?? 'nuevo'} idProveedor={p.id_proveedor} suministra={suministra} inicial={formProducto.inicial} listo={listoFormulario} cancelar={() => setFormProducto(null)} />
            )}
            {suministra.length === 0 ? (
              <Vacio titulo="Sin productos asociados">{edita ? 'Asocia los productos que vende este proveedor para poder pedírselos en una orden de compra.' : undefined}</Vacio>
            ) : (
              <table className="tabla">
                <thead><tr><th>Producto</th><th className="num">Precio de compra</th><th className="num">Entrega</th><th>Estado</th>{edita && <th><span className="solo-lector">Acciones</span></th>}</tr></thead>
                <tbody>
                  {suministra.map((s) => {
                    const nombre = producto(s.sku).nombre
                    const clave = `p:${s.sku}`
                    return (
                      <tr key={s.sku}>
                        <td>{nombre}<span className="secundario">{s.sku}</span></td>
                        <td className="num cifra">{dinero(s.precio_compra)}</td>
                        <td className="num cifra">{s.dias_entrega} {s.dias_entrega === 1 ? 'día' : 'días'}</td>
                        <td><EtiquetaEstado estado={s.estado} /></td>
                        {edita && (
                          <td>
                            {confirmar === clave ? (
                              <span className="acciones-fila envolver">
                                <span className="confirmar">¿Quitar {s.sku}?</span>
                                <button type="button" className="btn btn-sm btn-peligro" disabled={!!ocupado}
                                  onClick={() => accion(clave, () => proveedoresApi.eliminarProducto(p.id_proveedor, s.sku), `${nombre} ya no aparece como suministrado por ${p.razon_social}`)}>Quitar</button>
                                <button type="button" className="btn btn-sm btn-fantasma" onClick={() => setConfirmar(null)}>Cancelar</button>
                              </span>
                            ) : (
                              <span className="acciones-fila">
                                <button type="button" className="btn btn-sm btn-fantasma" aria-label={`Editar ${nombre}`} title="Editar precio y días" disabled={!!ocupado} onClick={() => { setFormProducto({ inicial: s }); setConfirmar(null) }}><Pencil size={16} aria-hidden /></button>
                                <button type="button" className={`btn btn-sm${s.estado === 'ACTIVO' ? ' btn-fantasma' : ''}`} disabled={!!ocupado}
                                  onClick={() => {
                                    const nuevo: Estado = s.estado === 'ACTIVO' ? 'INACTIVO' : 'ACTIVO'
                                    accion(clave, () => proveedoresApi.guardarProducto(p.id_proveedor, s.sku, { precio_compra: s.precio_compra, dias_entrega: s.dias_entrega, estado: nuevo }),
                                      nuevo === 'ACTIVO' ? `${nombre} vuelve a estar disponible para órdenes` : `${nombre} quedó inactivo con este proveedor`)
                                  }}>
                                  {s.estado === 'ACTIVO' ? 'Inactivar' : 'Activar'}
                                </button>
                                <button type="button" className="btn btn-sm btn-fantasma" aria-label={`Quitar ${nombre}`} title="Quitar" disabled={!!ocupado} onClick={() => setConfirmar(clave)}><Trash2 size={16} aria-hidden /></button>
                              </span>
                            )}
                          </td>
                        )}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </section>
          {verOrdenes && <section className="tabla-envoltura" aria-labelledby="t-oc">
            <div className="panel-titulo" style={{ padding: '16px 16px 0' }}><h2 id="t-oc">Órdenes de compra</h2></div>
            {!ordenes ? <Vacio titulo="No se pudieron consultar las órdenes">ms-compras no respondió; el resto del proveedor está al día.</Vacio> : ordenes.data.length === 0 ? <Vacio titulo="Sin órdenes con este proveedor" /> : (
              <table className="tabla">
                <thead><tr><th>Orden</th><th>Estado</th><th className="num">Total</th><th>Creada</th></tr></thead>
                <tbody>
                  {ordenes.data.map((o) => <tr key={o.id_orden}><td><Link className="doc" to={`/ordenes-compra/${o.id_orden}`}>{o.numero}</Link></td><td><EtiquetaOrden estado={o.estado} /></td><td className="num cifra">{dinero(o.total)}</td><td className="cifra">{fecha(o.fecha_creacion)}</td></tr>)}
                </tbody>
              </table>
            )}
          </section>}
        </div>
        <aside className="panel">
          <div className="panel-titulo">
            <h2>Contactos</h2>
            {edita && !formContacto && <button type="button" className="btn btn-sm" onClick={() => { setFormContacto(true); setConfirmar(null) }}><Plus size={16} aria-hidden />Agregar</button>}
          </div>
          {formContacto && <FormContacto idProveedor={p.id_proveedor} listo={listoFormulario} cancelar={() => setFormContacto(false)} />}
          {p.contactos.length === 0 ? <p>Sin contactos registrados.</p> : p.contactos.map((ct) => {
            const clave = `c:${ct.id_contacto}`
            return (
              <div key={ct.id_contacto} style={{ display: 'grid', gap: 4, padding: '12px 0', borderBottom: '1px solid var(--linea)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <strong style={{ fontSize: 'var(--t-l)' }}>{ct.nombre}</strong>
                  {edita && confirmar !== clave && (
                    <button type="button" className="btn btn-sm btn-fantasma" aria-label={`Eliminar el contacto ${ct.nombre}`} title="Eliminar contacto" disabled={!!ocupado} onClick={() => setConfirmar(clave)}><Trash2 size={16} aria-hidden /></button>
                  )}
                </div>
                <span style={{ color: 'var(--tinta-2)' }}>{ct.cargo}</span>
                <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}><Phone size={16} aria-hidden />{ct.telefono}</span>
                <a href={`mailto:${ct.email}`} style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}><Mail size={16} aria-hidden />{ct.email}</a>
                {confirmar === clave && (
                  <span className="acciones-fila envolver" style={{ marginTop: 4 }}>
                    <span className="confirmar">¿Eliminar a {ct.nombre}?</span>
                    <button type="button" className="btn btn-sm btn-peligro" disabled={!!ocupado}
                      onClick={() => accion(clave, () => proveedoresApi.eliminarContacto(p.id_proveedor, ct.id_contacto), `${ct.nombre} ya no es contacto de ${p.razon_social}`)}>Eliminar</button>
                    <button type="button" className="btn btn-sm btn-fantasma" onClick={() => setConfirmar(null)}>Cancelar</button>
                  </span>
                )}
              </div>
            )
          })}
          <dl className="datos" style={{ marginTop: 16 }}>
            <dt>Teléfono</dt><dd>{p.telefono}</dd>
            <dt>Correo</dt><dd>{p.email}</dd>
          </dl>
        </aside>
      </div>
    </>
  )
}

/**
 * Asocia un producto del catálogo al proveedor o actualiza su precio y días de entrega
 * (PUT /api/proveedores/{id}/productos/{sku}, que crea o reemplaza el renglón).
 */
function FormSuministro({ idProveedor, suministra, inicial, listo, cancelar }: {
  idProveedor: number
  suministra: ProductoSuministrado[]
  inicial?: ProductoSuministrado
  listo: (texto: string) => void
  cancelar: () => void
}) {
  const [sku, setSku] = useState(inicial?.sku ?? '')
  const [precio, setPrecio] = useState(inicial ? String(inicial.precio_compra) : '')
  const [dias, setDias] = useState(inicial ? String(inicial.dias_entrega) : '')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const existente = suministra.find((s) => s.sku === sku)
  const opciones = productos.filter((x) => x.estado === 'ACTIVO' || x.sku === inicial?.sku).sort((a, b) => a.sku.localeCompare(b.sku))

  const v = useValidacion(validar({
    sku: [reglas.requerido(sku, 'Elige el producto que suministra.')],
    precio_compra: [reglas.numero(precio, { requerido: true, mensajeVacio: 'Escribe el precio de compra.', decimales: 2, mayorQueCero: true, max: 100_000_000, mensajeMax: 'Revisa el precio: supera $ 100.000.000.' })],
    dias_entrega: [
      /[.,]/.test(dias) && 'Escribe un número entero de días.',
      reglas.numero(dias, { requerido: true, mensajeVacio: 'Escribe los días de entrega.', decimales: 0, min: 0, max: 365, mensajeMax: 'Revisa los días: supera un año.' }),
    ],
  }))
  const campos = { ...erroresCampo(error), ...v.visibles }

  /** Al elegir un producto que ya está asociado, se traen su precio y sus días para editarlos. */
  function elegir(nuevo: string) {
    setSku(nuevo)
    const previo = suministra.find((s) => s.sku === nuevo)
    if (previo) { setPrecio(String(previo.precio_compra)); setDias(String(previo.dias_entrega)) }
  }

  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!v.comprobar(e.currentTarget)) return
    setEnviando(true)
    setError(null)
    try {
      const r = await proveedoresApi.guardarProducto(idProveedor, sku, { precio_compra: aNumero(precio) ?? 0, dias_entrega: aNumero(dias) ?? 0, estado: 'ACTIVO' })
      listo(`${producto(r.sku).nombre} ${existente ? 'actualizado' : 'asociado'}: ${dinero(r.precio_compra)}, entrega en ${r.dias_entrega} ${r.dias_entrega === 1 ? 'día' : 'días'}`)
    } catch (err) {
      setError(err as Error)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form className="formulario" style={{ maxWidth: 'none', padding: 16, borderBottom: '1px solid var(--linea)' }} onSubmit={enviar} onBlur={v.alSalir} noValidate>
      {error && !Object.keys(erroresCampo(error)).length && <ErrorCaja error={error} />}
      <div className="fila-campos">
        <Campo id="ps-sku" etiqueta="Producto" error={campos.sku} ayuda={existente && !inicial ? 'Ya está asociado: se actualizarán su precio y sus días.' : undefined}>
          <select id="ps-sku" name="sku" value={sku} disabled={!!inicial} onChange={(e) => elegir(e.target.value)}>
            <option value="">Elige un producto del catálogo</option>
            {opciones.map((x) => <option key={x.sku} value={x.sku}>{x.sku} · {x.nombre}{suministra.some((s) => s.sku === x.sku) ? ' (asociado)' : ''}</option>)}
          </select>
        </Campo>
        <Campo id="ps-precio" etiqueta="Precio de compra" error={campos.precio_compra}>
          <input id="ps-precio" name="precio_compra" inputMode="decimal" maxLength={14} value={precio} onChange={(e) => setPrecio(e.target.value)} />
        </Campo>
        <Campo id="ps-dias" etiqueta="Días de entrega" error={campos.dias_entrega} ayuda="0 si entrega el mismo día.">
          <input id="ps-dias" name="dias_entrega" inputMode="numeric" maxLength={3} value={dias} onChange={(e) => setDias(e.target.value)} />
        </Campo>
      </div>
      <div className="acciones-separadas">
        <BotonEnvio enviando={enviando}>{existente ? 'Actualizar producto' : 'Asociar producto'}</BotonEnvio>
        <button type="button" className="btn btn-fantasma" onClick={cancelar}>Cancelar</button>
      </div>
    </form>
  )
}

/** Registra un contacto del proveedor (POST /api/proveedores/{id}/contactos). */
function FormContacto({ idProveedor, listo, cancelar }: { idProveedor: number; listo: (texto: string) => void; cancelar: () => void }) {
  const [v, setV] = useState({ nombre: '', cargo: '', telefono: '', email: '' })
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value })
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const val = useValidacion(validar({
    nombre: [reglas.requerido(v.nombre, 'Escribe el nombre del contacto.'), reglas.largo(v.nombre, 2, 120), reglas.nombrePersona(v.nombre)],
    cargo: [reglas.requerido(v.cargo, 'Escribe el cargo.'), reglas.largo(v.cargo, 2, 100)],
    telefono: [reglas.requerido(v.telefono, 'Escribe un teléfono de contacto.'), reglas.telefono(v.telefono)],
    email: [reglas.requerido(v.email, 'Escribe el correo del contacto.'), reglas.email(v.email)],
  }))
  const campos = { ...erroresCampo(error), ...val.visibles }

  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!val.comprobar(e.currentTarget)) return
    setEnviando(true)
    setError(null)
    try {
      const ct = await proveedoresApi.agregarContacto(idProveedor, { nombre: v.nombre.trim(), cargo: v.cargo.trim(), telefono: v.telefono.trim(), email: v.email.trim().toLowerCase() })
      listo(`${ct.nombre} quedó como contacto`)
    } catch (err) {
      setError(err as Error)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form className="formulario" style={{ padding: '12px 0 16px', borderBottom: '1px solid var(--linea)' }} onSubmit={enviar} onBlur={val.alSalir} noValidate>
      {error && !Object.keys(erroresCampo(error)).length && <ErrorCaja error={error} />}
      <Campo id="ct-nombre" etiqueta="Nombre" error={campos.nombre}><input id="ct-nombre" name="nombre" maxLength={120} autoComplete="off" value={v.nombre} onChange={set('nombre')} /></Campo>
      <Campo id="ct-cargo" etiqueta="Cargo" error={campos.cargo}><input id="ct-cargo" name="cargo" maxLength={100} value={v.cargo} onChange={set('cargo')} placeholder="Ejecutiva de ventas" /></Campo>
      <Campo id="ct-tel" etiqueta="Teléfono" error={campos.telefono}><input id="ct-tel" name="telefono" type="tel" maxLength={20} value={v.telefono} onChange={set('telefono')} /></Campo>
      <Campo id="ct-email" etiqueta="Correo" error={campos.email}><input id="ct-email" name="email" type="email" maxLength={150} value={v.email} onChange={set('email')} /></Campo>
      <div className="acciones-separadas">
        <BotonEnvio enviando={enviando}>Agregar contacto</BotonEnvio>
        <button type="button" className="btn btn-fantasma" onClick={cancelar}>Cancelar</button>
      </div>
    </form>
  )
}
