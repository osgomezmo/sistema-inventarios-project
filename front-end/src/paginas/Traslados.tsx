import { Fragment, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { ArrowRight, Plus } from 'lucide-react'
import { stockApi, trasladosApi } from '../api/cliente'
import { bodega as bodegaDe, nombreUsuario, producto, productoPorSku, productos } from '../api/maestros'
import { useUsuario } from '../auth/Sesion'
import { puedeEditar } from '../auth/permisos'
import { useAvisos } from '../contexto/Avisos'
import { useBodega } from '../contexto/Bodega'
import { useMaestros } from '../contexto/Maestros'
import { BotonEnvio, Campo, Cargando, Encabezado, ErrorCaja, Paginacion, Vacio, erroresCampo } from '../componentes/ui'
import { cantidad, fechaHora, numeroMovimiento, numeroTraslado, unidad } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'
import { aNumero, decimalesPorUnidad, reglas, useValidacion, validar } from '../lib/validacion'

export function Traslados() {
  const usuario = useUsuario()
  useMaestros()
  const [params, setParams] = useSearchParams()
  const page = Number(params.get('page') ?? 1)
  const c = useConsulta(() => trasladosApi.listar({ page }), [page])
  return (
    <>
      <Encabezado
        titulo="Traslados"
        descripcion="Cada traslado genera dos movimientos: la salida de la bodega de origen y la entrada en la de destino, al mismo costo promedio."
        acciones={puedeEditar(usuario.rol, 'movimientos') && <Link className="btn btn-pri" to="/traslados/nuevo"><Plus size={18} aria-hidden />Nuevo traslado</Link>}
      />
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      <div className="tabla-envoltura">
        {!c.datos && !c.error && <Cargando />}
        {c.datos && (c.datos.data.length === 0 ? <Vacio titulo="Aún no hay traslados" /> : (
          <>
            <table className="tabla">
              <thead><tr><th>Traslado</th><th>Fecha</th><th>Producto</th><th>Ruta</th><th className="num">Cantidad</th><th>Movimientos</th><th>Motivo</th><th>Usuario</th></tr></thead>
              <tbody>
                {c.datos.data.map((t) => {
                  const p = producto(t.sku)
                  return (
                    <tr key={t.id_traslado}>
                      <td className="doc">{numeroTraslado(t.id_traslado)}</td>
                      <td className="cifra">{fechaHora(t.fecha)}</td>
                      <td>{p.nombre}<span className="secundario">{t.sku}</span></td>
                      <td><span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 700 }}>{bodegaDe(t.id_bodega_origen).codigo}<ArrowRight size={16} aria-label="hacia" />{bodegaDe(t.id_bodega_destino).codigo}</span></td>
                      <td className="num cifra">{cantidad(t.cantidad, p.unidad_medida)}</td>
                      <td>{t.movimientos.salida ? numeroMovimiento(t.movimientos.salida) : '—'}<span className="secundario">{t.movimientos.entrada ? numeroMovimiento(t.movimientos.entrada) : '—'}</span></td>
                      <td>{t.motivo ?? '—'}</td>
                      <td>{nombreUsuario(t.id_usuario)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <Paginacion meta={c.datos.meta} cambiar={(n) => setParams({ page: String(n) })} />
          </>
        ))}
      </div>
    </>
  )
}

export function NuevoTraslado() {
  const usuario = useUsuario()
  const { idBodega, activas } = useBodega()
  const navegar = useNavigate()
  const avisar = useAvisos()
  const [sku, setSku] = useState('')
  const [origen, setOrigen] = useState(idBodega)
  const [destino, setDestino] = useState(activas.find((b) => b.id_bodega !== idBodega)?.id_bodega ?? idBodega)
  const [cant, setCant] = useState('')
  const [motivo, setMotivo] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const p = productoPorSku.get(sku)
  // Saldos del producto en todas las bodegas, para el tope de la cantidad y el panel lateral.
  const consultaSaldos = useConsulta(() => (sku ? stockApi.todos({ sku }) : Promise.resolve([])), [sku])
  const saldos = consultaSaldos.datos ?? []
  const disponible = saldos.find((s) => s.id_bodega === origen)?.cantidad ?? 0

  const v = useValidacion(validar({
    sku: [reglas.requerido(sku, 'Elige el producto que se traslada.')],
    id_bodega_destino: [origen === destino && 'Elige una bodega distinta a la de origen.'],
    cantidad: [reglas.numero(cant, {
      requerido: true,
      mensajeVacio: 'Escribe la cantidad a trasladar.',
      decimales: p ? decimalesPorUnidad(p.unidad_medida) : 3,
      mayorQueCero: true,
      max: p && consultaSaldos.datos ? disponible : undefined,
      mensajeMax: p && `En la bodega de origen solo hay ${cantidad(disponible, p.unidad_medida)}.`,
    })],
    motivo: [reglas.largo(motivo, 0, 200)],
  }))
  const campos = { ...erroresCampo(error), ...v.visibles }

  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!v.comprobar(e.currentTarget)) return
    setEnviando(true)
    setError(null)
    try {
      const t = await trasladosApi.crear({ sku, id_bodega_origen: origen, id_bodega_destino: destino, cantidad: aNumero(cant) ?? 0, motivo })
      avisar(`${numeroTraslado(t.id_traslado)} registrado: ${cantidad(t.cantidad, producto(t.sku).unidad_medida)} de ${bodegaDe(origen).codigo} a ${bodegaDe(destino).codigo}`)
      navegar('/traslados')
    } catch (err) {
      setError(err as Error)
    } finally {
      setEnviando(false)
    }
  }

  if (!puedeEditar(usuario.rol, 'movimientos')) return <Vacio titulo="Tu rol solo puede consultar traslados" />

  return (
    <>
      <Encabezado migas={<><Link to="/traslados">Traslados</Link><span aria-hidden>/</span><span>Nuevo</span></>} titulo="Nuevo traslado" />
      <div className="dos-columnas">
        <form className="panel formulario" onSubmit={enviar} onBlur={v.alSalir} noValidate>
          {error && !Object.keys(erroresCampo(error)).length && <ErrorCaja error={error} />}
          <Campo id="t-sku" etiqueta="Producto" error={campos.sku}>
            <select id="t-sku" name="sku" value={sku} onChange={(e) => setSku(e.target.value)}>
              <option value="">Elige un producto</option>
              {productos.filter((x) => x.estado === 'ACTIVO').map((x) => <option key={x.sku} value={x.sku}>{x.sku} · {x.nombre}</option>)}
            </select>
          </Campo>
          <div className="fila-campos">
            <Campo id="t-origen" etiqueta="Bodega de origen">
              <select id="t-origen" value={origen} onChange={(e) => setOrigen(Number(e.target.value))}>
                {activas.map((b) => <option key={b.id_bodega} value={b.id_bodega}>{b.codigo} · {b.nombre}</option>)}
              </select>
            </Campo>
            <Campo id="t-destino" etiqueta="Bodega de destino" error={campos.id_bodega_destino}>
              <select id="t-destino" name="id_bodega_destino" value={destino} onChange={(e) => setDestino(Number(e.target.value))}>
                {activas.map((b) => <option key={b.id_bodega} value={b.id_bodega}>{b.codigo} · {b.nombre}</option>)}
              </select>
            </Campo>
          </div>
          <Campo id="t-cant" etiqueta={`Cantidad${p ? ` (${unidad(p.unidad_medida)})` : ''}`} error={campos.cantidad} ayuda={p ? `Disponible en origen: ${cantidad(disponible, p.unidad_medida)}` : undefined}>
            <input id="t-cant" name="cantidad" inputMode="decimal" maxLength={14} value={cant} onChange={(e) => setCant(e.target.value)} />
          </Campo>
          <Campo id="t-motivo" etiqueta="Motivo" opcional error={campos.motivo}>
            <textarea id="t-motivo" name="motivo" maxLength={200} value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Reposición de la bodega de despacho" />
          </Campo>
          <div className="acciones-separadas">
            <BotonEnvio enviando={enviando}>Registrar traslado</BotonEnvio>
            <Link className="btn btn-fantasma" to="/traslados">Cancelar</Link>
          </div>
        </form>
        <aside className="panel">
          <h2>Saldo por bodega</h2>
          {!p ? <p>Elige un producto para ver dónde hay saldo.</p> : consultaSaldos.error ? <ErrorCaja error={consultaSaldos.error} reintentar={consultaSaldos.recargar} /> : consultaSaldos.cargando ? <Cargando filas={4} texto="Consultando saldos" /> : (
            <dl className="datos">
              {activas.map((b) => (
                <Fragment key={b.id_bodega}>
                  <dt>{b.codigo} · {b.nombre}</dt>
                  <dd>{cantidad(saldos.find((s) => s.id_bodega === b.id_bodega)?.cantidad ?? 0, p.unidad_medida)}</dd>
                </Fragment>
              ))}
            </dl>
          )}
        </aside>
      </div>
    </>
  )
}
