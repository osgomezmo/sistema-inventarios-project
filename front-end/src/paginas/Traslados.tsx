import { Fragment, useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { ArrowRight, Plus } from 'lucide-react'
import { trasladosApi } from '../api/cliente'
import { bodegaPorId, productoPorSku, productos, usuarioPorId } from '../api/mock/maestros'
import { saldosActuales } from '../api/mock/simulacion'
import { useUsuario } from '../auth/Sesion'
import { puedeEditar } from '../auth/permisos'
import { useAvisos } from '../contexto/Avisos'
import { useBodega } from '../contexto/Bodega'
import { BotonEnvio, Campo, Cargando, Encabezado, ErrorCaja, Vacio, erroresCampo } from '../componentes/ui'
import { cantidad, fechaHora, numeroMovimiento, numeroTraslado, unidad } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'

export function Traslados() {
  const usuario = useUsuario()
  const c = useConsulta(() => trasladosApi.listar(), [])
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
          <table className="tabla">
            <thead><tr><th>Traslado</th><th>Fecha</th><th>Producto</th><th>Ruta</th><th className="num">Cantidad</th><th>Movimientos</th><th>Motivo</th><th>Usuario</th></tr></thead>
            <tbody>
              {c.datos.data.map((t) => {
                const p = productoPorSku.get(t.sku)!
                return (
                  <tr key={t.id_traslado}>
                    <td className="doc">{numeroTraslado(t.id_traslado)}</td>
                    <td className="cifra">{fechaHora(t.fecha)}</td>
                    <td>{p.nombre}<span className="secundario">{t.sku}</span></td>
                    <td><span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 700 }}>{bodegaPorId.get(t.id_bodega_origen)!.codigo}<ArrowRight size={16} aria-label="hacia" />{bodegaPorId.get(t.id_bodega_destino)!.codigo}</span></td>
                    <td className="num cifra">{cantidad(t.cantidad, p.unidad_medida)}</td>
                    <td>{numeroMovimiento(t.movimientos.salida)}<span className="secundario">{numeroMovimiento(t.movimientos.entrada)}</span></td>
                    <td>{t.motivo ?? '—'}</td>
                    <td>{usuarioPorId.get(t.id_usuario)?.nombre}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
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
  const [destino, setDestino] = useState(activas.find((b) => b.id_bodega !== idBodega)!.id_bodega)
  const [cant, setCant] = useState('')
  const [motivo, setMotivo] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const campos = erroresCampo(error)
  const p = productoPorSku.get(sku)
  const saldos = useMemo(() => saldosActuales().filter((s) => s.sku === sku), [sku])
  const disponible = saldos.find((s) => s.id_bodega === origen)?.cantidad ?? 0

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      const t = await trasladosApi.crear({ sku, id_bodega_origen: origen, id_bodega_destino: destino, cantidad: Number(cant.replace(',', '.')), motivo }, usuario.id)
      avisar(`${numeroTraslado(t.id_traslado)} registrado: ${cantidad(t.cantidad, p!.unidad_medida)} de ${bodegaPorId.get(origen)!.codigo} a ${bodegaPorId.get(destino)!.codigo}`)
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
        <form className="panel formulario" onSubmit={enviar} noValidate>
          {error && !Object.keys(campos).length && <ErrorCaja error={error} />}
          <Campo id="t-sku" etiqueta="Producto" error={campos.sku}>
            <select id="t-sku" value={sku} onChange={(e) => setSku(e.target.value)}>
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
              <select id="t-destino" value={destino} onChange={(e) => setDestino(Number(e.target.value))}>
                {activas.map((b) => <option key={b.id_bodega} value={b.id_bodega}>{b.codigo} · {b.nombre}</option>)}
              </select>
            </Campo>
          </div>
          <Campo id="t-cant" etiqueta={`Cantidad${p ? ` (${unidad(p.unidad_medida)})` : ''}`} error={campos.cantidad} ayuda={p ? `Disponible en origen: ${cantidad(disponible, p.unidad_medida)}` : undefined}>
            <input id="t-cant" inputMode="decimal" value={cant} onChange={(e) => setCant(e.target.value)} />
          </Campo>
          <Campo id="t-motivo" etiqueta="Motivo" opcional>
            <textarea id="t-motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Reposición de la bodega de despacho" />
          </Campo>
          <div className="acciones-separadas">
            <BotonEnvio enviando={enviando}>Registrar traslado</BotonEnvio>
            <Link className="btn btn-fantasma" to="/traslados">Cancelar</Link>
          </div>
        </form>
        <aside className="panel">
          <h2>Saldo por bodega</h2>
          {!p ? <p>Elige un producto para ver dónde hay saldo.</p> : (
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
