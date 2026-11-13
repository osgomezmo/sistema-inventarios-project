import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { Check, PackageCheck, Plus, Trash2, TriangleAlert, Undo2 } from 'lucide-react'
import type { EstadoOrden, OrdenCompra } from '../api/types'
import { ordenesApi, proveedoresApi } from '../api/cliente'
import { bodegaPorId, productoPorSku, proveedorPorId, proveedores, usuarioPorId } from '../api/mock/maestros'
import { useUsuario } from '../auth/Sesion'
import { puedeEditar } from '../auth/permisos'
import { useAvisos } from '../contexto/Avisos'
import { useBodega } from '../contexto/Bodega'
import { BotonEnvio, Campo, Cargando, Encabezado, ErrorCaja, ErrorCelda, EtiquetaOrden, Paginacion, Vacio, erroresCampo } from '../componentes/ui'
import { aNumero, decimalesPorUnidad, reglas, useValidacion, validar } from '../lib/validacion'
import { cantidad, dinero, fecha, fechaHora, nombreEstadoOrden } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'

const ESTADOS: EstadoOrden[] = ['BORRADOR', 'APROBADA', 'RECIBIDA_PARCIAL', 'RECIBIDA', 'ANULADA']

export function Ordenes() {
  const usuario = useUsuario()
  const [params, setParams] = useSearchParams()
  const estado = (params.get('estado') as EstadoOrden) || undefined
  const page = Number(params.get('page') ?? 1)
  const c = useConsulta(() => ordenesApi.listar({ estado, page }), [estado, page])

  return (
    <>
      <Encabezado
        titulo="Órdenes de compra"
        descripcion="Borrador, aprobada, recibida parcialmente, recibida o anulada. Al recibir, la mercancía entra al stock de la bodega destino."
        acciones={puedeEditar(usuario.rol, 'ordenes') && <Link className="btn btn-pri" to="/ordenes-compra/nueva"><Plus size={18} aria-hidden />Nueva orden de compra</Link>}
      />
      <div className="chips" role="group" aria-label="Estado">
        <button type="button" className="chip" aria-pressed={!estado} onClick={() => setParams({})}>Todas</button>
        {ESTADOS.map((e) => <button key={e} type="button" className="chip" aria-pressed={estado === e} onClick={() => setParams({ estado: e })}>{nombreEstadoOrden[e]}</button>)}
      </div>
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      <div className="tabla-envoltura">
        {!c.datos && !c.error && <Cargando />}
        {c.datos && (c.datos.data.length === 0 ? <Vacio titulo={`Ninguna orden ${estado ? nombreEstadoOrden[estado].toLowerCase() : ''}`} /> : (
          <>
            <table className="tabla">
              <thead><tr><th>Orden</th><th>Proveedor</th><th>Bodega destino</th><th>Estado</th><th className="num">Recibido</th><th className="num">Total</th><th>Actualizada</th></tr></thead>
              <tbody>
                {c.datos.data.map((o) => {
                  const pedido = o.items.reduce((a, i) => a + i.cantidad, 0)
                  const recibido = o.items.reduce((a, i) => a + i.cantidad_recibida, 0)
                  return (
                    <tr key={o.id_orden}>
                      <td><Link className="doc" to={`/ordenes-compra/${o.id_orden}`}>{o.numero}</Link><span className="secundario">{o.items.length} productos</span></td>
                      <td>{proveedorPorId.get(o.id_proveedor)!.razon_social}</td>
                      <td>{bodegaPorId.get(o.id_bodega_destino)!.codigo} · {bodegaPorId.get(o.id_bodega_destino)!.nombre}</td>
                      <td><EtiquetaOrden estado={o.estado} /></td>
                      <td className="num cifra">{pedido ? Math.round((recibido / pedido) * 100) : 0} %</td>
                      <td className="num cifra">{dinero(o.total)}</td>
                      <td className="cifra">{fecha(o.fecha_actualizacion)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <Paginacion meta={c.datos.meta} cambiar={(n) => setParams({ ...(estado ? { estado } : {}), page: String(n) })} />
          </>
        ))}
      </div>
    </>
  )
}

const FLUJO: EstadoOrden[] = ['BORRADOR', 'APROBADA', 'RECIBIDA_PARCIAL', 'RECIBIDA']

export function OrdenDetalle() {
  const { id = '' } = useParams()
  const usuario = useUsuario()
  const avisar = useAvisos()
  const c = useConsulta(() => ordenesApi.obtener(Number(id)), [id])
  const [panel, setPanel] = useState<'recibir' | 'devolver' | 'anular' | null>(null)
  const [accionError, setAccionError] = useState<Error | null>(null)

  if (c.error) return <ErrorCaja error={c.error} reintentar={c.recargar} />
  if (!c.datos) return <div className="panel"><Cargando /></div>
  const o = c.datos
  const prov = proveedorPorId.get(o.id_proveedor)!
  const puedeAprobar = puedeEditar(usuario.rol, 'aprobarOrdenes') && o.estado === 'BORRADOR'
  const puedeRecibir = puedeEditar(usuario.rol, 'recibirMercancia') && ['APROBADA', 'RECIBIDA_PARCIAL'].includes(o.estado)
  const puedeDevolver = puedeEditar(usuario.rol, 'devolucionProveedor') && o.items.some((i) => i.cantidad_recibida > i.cantidad_devuelta)
  const puedeAnular = puedeEditar(usuario.rol, 'aprobarOrdenes') && ['BORRADOR', 'APROBADA'].includes(o.estado) && o.recepciones.length === 0

  async function aprobar() {
    setAccionError(null)
    try { await ordenesApi.aprobar(o.id_orden); avisar(`${o.numero} aprobada`); c.recargar() } catch (e) { setAccionError(e as Error) }
  }
  const terminado = (texto: string) => { avisar(texto); setPanel(null); c.recargar() }
  const paso = o.estado === 'ANULADA' ? -1 : FLUJO.indexOf(o.estado)

  return (
    <>
      <Encabezado
        migas={<><Link to="/ordenes-compra">Órdenes de compra</Link><span aria-hidden>/</span><span>{o.numero}</span></>}
        titulo={o.numero}
        descripcion={<>{prov.razon_social} · destino {bodegaPorId.get(o.id_bodega_destino)!.nombre} · creada el {fecha(o.fecha_creacion)} por {usuarioPorId.get(o.id_usuario)?.nombre}</>}
        acciones={<EtiquetaOrden estado={o.estado} />}
      />

      <ol className="flujo-orden" aria-label="Estado de la orden">
        {FLUJO.map((e, i) => (
          <li key={e} data-estado={o.estado === 'ANULADA' ? 'anulado' : i < paso ? 'hecho' : i === paso ? 'actual' : 'pendiente'}>
            <span className="flujo-marca">{i < paso ? <Check size={16} aria-hidden /> : i + 1}</span>
            {nombreEstadoOrden[e]}
          </li>
        ))}
        {o.estado === 'ANULADA' && <li data-estado="anulada"><span className="flujo-marca">×</span>Anulada: {o.motivo_anulacion}</li>}
      </ol>

      {(puedeAprobar || puedeRecibir || puedeDevolver || puedeAnular) && (
        <div className="acciones-separadas" style={{ marginBottom: 20 }}>
          {puedeAprobar && <button type="button" className="btn btn-pri" onClick={aprobar}><Check size={18} aria-hidden />Aprobar orden</button>}
          {puedeRecibir && <button type="button" className={`btn ${puedeAprobar ? '' : 'btn-pri'}`} aria-expanded={panel === 'recibir'} onClick={() => setPanel(panel === 'recibir' ? null : 'recibir')}><PackageCheck size={18} aria-hidden />Recibir mercancía</button>}
          {puedeDevolver && <button type="button" className="btn" aria-expanded={panel === 'devolver'} onClick={() => setPanel(panel === 'devolver' ? null : 'devolver')}><Undo2 size={18} aria-hidden />Devolver a proveedor</button>}
          {puedeAnular && <span className="aparte"><button type="button" className="btn btn-peligro" aria-expanded={panel === 'anular'} onClick={() => setPanel(panel === 'anular' ? null : 'anular')}>Anular orden</button></span>}
        </div>
      )}
      {accionError && <ErrorCaja error={accionError} />}

      {panel === 'recibir' && <FormCantidades o={o} modo="recibir" listo={terminado} cancelar={() => setPanel(null)} />}
      {panel === 'devolver' && <FormCantidades o={o} modo="devolver" listo={terminado} cancelar={() => setPanel(null)} />}
      {panel === 'anular' && <FormAnular o={o} listo={terminado} cancelar={() => setPanel(null)} />}

      <div className="dos-columnas">
        <section className="tabla-envoltura" aria-labelledby="t-items">
          <div className="panel-titulo" style={{ padding: '16px 16px 0' }}><h2 id="t-items">Productos</h2></div>
          <table className="tabla">
            <thead><tr><th>Producto</th><th className="num">Pedido</th><th className="num">Recibido</th><th className="num">Devuelto</th><th className="num">Precio u.</th><th className="num">Subtotal</th></tr></thead>
            <tbody>
              {o.items.map((i) => {
                const p = productoPorSku.get(i.sku)!
                return (
                  <tr key={i.id_detalle}>
                    <td>{p.nombre}<span className="secundario">{i.sku}</span></td>
                    <td className="num cifra">{cantidad(i.cantidad, p.unidad_medida)}</td>
                    <td className="num cifra">{cantidad(i.cantidad_recibida, p.unidad_medida)}</td>
                    <td className="num cifra">{i.cantidad_devuelta ? cantidad(i.cantidad_devuelta, p.unidad_medida) : '—'}</td>
                    <td className="num cifra">{dinero(i.precio_unitario)}</td>
                    <td className="num cifra">{dinero(i.cantidad * i.precio_unitario)}</td>
                  </tr>
                )
              })}
            </tbody>
            <tfoot><tr><td colSpan={5}><strong>Total</strong></td><td className="num cifra"><strong>{dinero(o.total)}</strong></td></tr></tfoot>
          </table>
        </section>
        <aside className="pila">
          <section className="panel">
            <h2>Recepciones</h2>
            {o.recepciones.length === 0 ? <p>Aún no se ha recibido mercancía.</p> : o.recepciones.map((r) => (
              <div key={r.id_recepcion} style={{ padding: '10px 0', borderBottom: '1px solid var(--linea)' }}>
                <strong>{fechaHora(r.fecha)}</strong> · {usuarioPorId.get(r.id_usuario)?.nombre}
                <p style={{ color: 'var(--tinta-2)' }}>{r.observaciones}</p>
              </div>
            ))}
          </section>
          {o.devoluciones.length > 0 && (
            <section className="panel">
              <h2>Devoluciones al proveedor</h2>
              {o.devoluciones.map((d) => <p key={d.id_devolucion}><strong>{fechaHora(d.fecha)}</strong> · {d.motivo}</p>)}
            </section>
          )}
        </aside>
      </div>
    </>
  )
}

function FormCantidades({ o, modo, listo, cancelar }: { o: OrdenCompra; modo: 'recibir' | 'devolver'; listo: (t: string) => void; cancelar: () => void }) {
  const usuario = useUsuario()
  const [cant, setCant] = useState<Record<number, string>>({})
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const recibir = modo === 'recibir'
  const disponible = (i: OrdenCompra['items'][number]) => (recibir ? i.cantidad - i.cantidad_recibida : i.cantidad_recibida - i.cantidad_devuelta)

  const conSaldo = o.items.filter((i) => disponible(i) > 0)
  const v = useValidacion(validar({
    ...Object.fromEntries(conSaldo.map((i) => {
      const p = productoPorSku.get(i.sku)!
      return [`c-${i.id_detalle}`, [reglas.numero(cant[i.id_detalle] ?? '', {
        decimales: decimalesPorUnidad(p.unidad_medida),
        min: 0,
        max: disponible(i),
        mensajeMax: recibir ? `Quedan ${cantidad(disponible(i), p.unidad_medida)} por recibir.` : `Solo se pueden devolver ${cantidad(disponible(i), p.unidad_medida)}.`,
      })]]
    })),
    items: [!conSaldo.some((i) => (aNumero(cant[i.id_detalle] ?? '') ?? 0) > 0) && (recibir ? 'Escribe al menos una cantidad recibida.' : 'Escribe al menos una cantidad a devolver.')],
    texto: recibir ? [reglas.largo(texto, 0, 300)] : [reglas.requerido(texto, 'Indica el motivo de la devolución.'), reglas.largo(texto, 5, 200)],
  }))

  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!v.comprobar(e.currentTarget)) return
    setEnviando(true)
    setError(null)
    const items = o.items.map((i) => ({ id_detalle: i.id_detalle, cantidad: aNumero(cant[i.id_detalle] ?? '') ?? 0 }))
    try {
      const r = recibir ? await ordenesApi.recibir(o.id_orden, items, texto, usuario.id) : await ordenesApi.devolver(o.id_orden, items, texto, usuario.id)
      listo(recibir ? `Mercancía recibida: ${r.numero} quedó ${nombreEstadoOrden[r.estado].toLowerCase()}` : `Devolución registrada en ${r.numero}`)
    } catch (err) {
      setError(err as Error)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form className="panel formulario" style={{ maxWidth: 'none', marginBottom: 20 }} onSubmit={enviar} onBlur={v.alSalir} noValidate>
      <h2>{recibir ? 'Recibir mercancía' : 'Devolver a proveedor'}</h2>
      {error && <ErrorCaja error={error} />}
      <table className="tabla recepcion-tabla">
        <thead><tr><th>Producto</th><th className="num">{recibir ? 'Pendiente' : 'Devolvible'}</th><th className="num">{recibir ? 'Cantidad recibida' : 'Cantidad a devolver'}</th></tr></thead>
        <tbody>
          {conSaldo.map((i) => {
            const p = productoPorSku.get(i.sku)!
            const clave = `c-${i.id_detalle}`
            return (
              <tr key={i.id_detalle}>
                <td>{p.nombre}<span className="secundario">{i.sku}</span></td>
                <td className="num cifra">{cantidad(disponible(i), p.unidad_medida)}</td>
                <td className="num">
                  <label className="solo-lector" htmlFor={clave}>Cantidad de {p.nombre}</label>
                  <input id={clave} name={clave} className="entrada" inputMode="decimal" maxLength={14} value={cant[i.id_detalle] ?? ''} placeholder="0"
                    aria-invalid={!!v.visibles[clave] || undefined} aria-describedby={v.visibles[clave] ? `${clave}-error` : undefined}
                    onChange={(e) => setCant({ ...cant, [i.id_detalle]: e.target.value })} />
                  <ErrorCelda id={`${clave}-error`} error={v.visibles[clave]} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <ErrorCelda id="c-items-error" error={v.visibles.items} />
      <Campo id="c-texto" etiqueta={recibir ? 'Observaciones' : 'Motivo'} opcional={recibir} error={v.visibles.texto}>
        <textarea id="c-texto" name="texto" maxLength={recibir ? 300 : 200} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder={recibir ? 'Temperatura de llegada, novedades del despacho' : 'Producto no conforme o en mal estado'} />
      </Campo>
      <div className="acciones-separadas">
        <BotonEnvio enviando={enviando}>{recibir ? 'Registrar recepción' : 'Registrar devolución'}</BotonEnvio>
        <button type="button" className="btn btn-fantasma" onClick={cancelar}>Cancelar</button>
      </div>
    </form>
  )
}

function FormAnular({ o, listo, cancelar }: { o: OrdenCompra; listo: (t: string) => void; cancelar: () => void }) {
  const [motivo, setMotivo] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const v = useValidacion(validar({ motivo: [reglas.requerido(motivo, 'Indica por qué se anula la orden.'), reglas.largo(motivo, 10, 200)] }))
  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!v.comprobar(e.currentTarget)) return
    setEnviando(true)
    try { await ordenesApi.anular(o.id_orden, motivo.trim()); listo(`${o.numero} anulada`) } catch (err) { setError(err as Error) } finally { setEnviando(false) }
  }
  return (
    <form className="panel formulario" style={{ marginBottom: 20 }} onSubmit={enviar} onBlur={v.alSalir} noValidate>
      <h2>Anular {o.numero}</h2>
      <div className="aviso aviso-error"><TriangleAlert size={20} aria-hidden /><div><strong>No se puede deshacer</strong><p>La orden queda en el historial con su motivo y ya no se podrá recibir.</p></div></div>
      <Campo id="a-motivo" etiqueta="Motivo de la anulación" error={v.visibles.motivo ?? erroresCampo(error).motivo} ayuda="Entre 10 y 200 caracteres.">
        <textarea id="a-motivo" name="motivo" maxLength={200} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </Campo>
      <div className="acciones-separadas">
        <BotonEnvio enviando={enviando} className="btn btn-peligro">Anular orden</BotonEnvio>
        <button type="button" className="btn btn-fantasma" onClick={cancelar}>Volver sin anular</button>
      </div>
    </form>
  )
}

export function NuevaOrden() {
  const usuario = useUsuario()
  const { idBodega, activas } = useBodega()
  const navegar = useNavigate()
  const avisar = useAvisos()
  const activos = proveedores.filter((p) => p.estado === 'ACTIVO')
  const [proveedor, setProveedor] = useState(activos[0].id_proveedor)
  const [bodega, setBodega] = useState(idBodega)
  const [items, setItems] = useState<Array<{ sku: string; cantidad: string; precio: string }>>([{ sku: '', cantidad: '', precio: '' }])
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const sumin = useConsulta(() => proveedoresApi.productos(proveedor), [proveedor])
  const num = (s: string) => aNumero(s) ?? 0
  const total = items.reduce((a, i) => a + num(i.cantidad) * num(i.precio), 0)

  const repetido = (sku: string) => !!sku && items.filter((i) => i.sku === sku).length > 1
  const v = useValidacion(validar({
    id_proveedor: [reglas.requerido(proveedor, 'Elige un proveedor activo.')],
    ...Object.fromEntries(items.flatMap((it, n) => {
      const p = productoPorSku.get(it.sku)
      return [
        [`item-${n}-sku`, [reglas.requerido(it.sku, 'Elige un producto o quita la fila.'), repetido(it.sku) && 'Este producto ya está en otra fila.']],
        [`item-${n}-cantidad`, [reglas.numero(it.cantidad, { requerido: true, mensajeVacio: 'Escribe la cantidad.', decimales: p ? decimalesPorUnidad(p.unidad_medida) : 3, mayorQueCero: true, max: 100000, mensajeMax: 'Revisa la cantidad: supera 100.000.' })]],
        [`item-${n}-precio`, [reglas.numero(it.precio, { requerido: true, mensajeVacio: 'Escribe el precio.', decimales: 2, mayorQueCero: true })]],
      ]
    })),
  }))
  const campos = { ...erroresCampo(error), ...v.visibles }

  const fijar = (n: number, cambio: Partial<{ sku: string; cantidad: string; precio: string }>) =>
    setItems(items.map((it, i) => (i === n ? { ...it, ...cambio } : it)))

  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!v.comprobar(e.currentTarget)) return
    setEnviando(true)
    setError(null)
    try {
      const o = await ordenesApi.crear({ id_proveedor: proveedor, id_bodega_destino: bodega, items: items.map((i) => ({ sku: i.sku, cantidad: num(i.cantidad), precio_unitario: num(i.precio) })) }, usuario.id)
      avisar(`${o.numero} creada en borrador`, { a: `/ordenes-compra/${o.id_orden}`, texto: 'Ver orden' })
      navegar(`/ordenes-compra/${o.id_orden}`)
    } catch (err) {
      setError(err as Error)
    } finally {
      setEnviando(false)
    }
  }

  if (!puedeEditar(usuario.rol, 'ordenes')) return <Vacio titulo="Tu rol solo puede consultar órdenes de compra" />

  return (
    <>
      <Encabezado migas={<><Link to="/ordenes-compra">Órdenes de compra</Link><span aria-hidden>/</span><span>Nueva</span></>} titulo="Nueva orden de compra" descripcion="Se guarda en borrador; el gerente o el administrador la aprueban antes de recibirla." />
      <form className="panel formulario" style={{ maxWidth: 960 }} onSubmit={enviar} onBlur={v.alSalir} noValidate>
        {error && !Object.keys(erroresCampo(error)).length && <ErrorCaja error={error} />}
        <div className="fila-campos">
          <Campo id="o-prov" etiqueta="Proveedor" error={campos.id_proveedor}>
            <select id="o-prov" value={proveedor} onChange={(e) => { setProveedor(Number(e.target.value)); setItems([{ sku: '', cantidad: '', precio: '' }]) }}>
              {activos.map((p) => <option key={p.id_proveedor} value={p.id_proveedor}>{p.razon_social}</option>)}
            </select>
          </Campo>
          <Campo id="o-bodega" etiqueta="Bodega destino">
            <select id="o-bodega" value={bodega} onChange={(e) => setBodega(Number(e.target.value))}>
              {activas.map((b) => <option key={b.id_bodega} value={b.id_bodega}>{b.codigo} · {b.nombre}</option>)}
            </select>
          </Campo>
        </div>
        <table className="tabla recepcion-tabla">
          <thead><tr><th>Producto</th><th className="num">Cantidad</th><th className="num">Precio unitario</th><th className="num">Subtotal</th><th><span className="solo-lector">Quitar</span></th></tr></thead>
          <tbody>
            {items.map((it, n) => {
              const k = { sku: `item-${n}-sku`, cantidad: `item-${n}-cantidad`, precio: `item-${n}-precio` }
              const aria = (clave: string) => ({ 'aria-invalid': !!campos[clave] || undefined, 'aria-describedby': campos[clave] ? `${clave}-error` : undefined })
              return (
              <tr key={n}>
                <td>
                  <label className="solo-lector" htmlFor={`o-sku-${n}`}>Producto {n + 1}</label>
                  <select id={`o-sku-${n}`} name={k.sku} className="entrada" value={it.sku} {...aria(k.sku)} onChange={(e) => fijar(n, { sku: e.target.value, precio: String(sumin.datos?.find((s) => s.sku === e.target.value)?.precio_compra ?? '') })}>
                    <option value="">Elige un producto del proveedor</option>
                    {(sumin.datos ?? []).map((s) => <option key={s.sku} value={s.sku}>{s.sku} · {productoPorSku.get(s.sku)!.nombre}</option>)}
                  </select>
                  <ErrorCelda id={`${k.sku}-error`} error={campos[k.sku]} />
                </td>
                <td className="num">
                  <label className="solo-lector" htmlFor={`o-c-${n}`}>Cantidad</label>
                  <input id={`o-c-${n}`} name={k.cantidad} className="entrada" inputMode="decimal" maxLength={14} value={it.cantidad} {...aria(k.cantidad)} onChange={(e) => fijar(n, { cantidad: e.target.value })} />
                  <ErrorCelda id={`${k.cantidad}-error`} error={campos[k.cantidad]} />
                </td>
                <td className="num">
                  <label className="solo-lector" htmlFor={`o-p-${n}`}>Precio</label>
                  <input id={`o-p-${n}`} name={k.precio} className="entrada" inputMode="decimal" maxLength={14} value={it.precio} {...aria(k.precio)} onChange={(e) => fijar(n, { precio: e.target.value })} />
                  <ErrorCelda id={`${k.precio}-error`} error={campos[k.precio]} />
                </td>
                <td className="num cifra">{dinero(num(it.cantidad) * num(it.precio))}</td>
                <td>{items.length > 1 && <button type="button" className="btn btn-fantasma btn-sm" aria-label={`Quitar producto ${n + 1}`} onClick={() => setItems(items.filter((_, i) => i !== n))}><Trash2 size={18} aria-hidden /></button>}</td>
              </tr>
              )
            })}
          </tbody>
          <tfoot><tr><td colSpan={3}><strong>Total</strong></td><td className="num cifra"><strong>{dinero(total)}</strong></td><td /></tr></tfoot>
        </table>
        <ErrorCelda id="o-items-error" error={campos.items} />
        <div><button type="button" className="btn btn-sm" onClick={() => setItems([...items, { sku: '', cantidad: '', precio: '' }])}><Plus size={16} aria-hidden />Agregar producto</button></div>
        <div className="acciones-separadas">
          <BotonEnvio enviando={enviando}>Guardar en borrador</BotonEnvio>
          <Link className="btn btn-fantasma" to="/ordenes-compra">Cancelar</Link>
        </div>
      </form>
    </>
  )
}
