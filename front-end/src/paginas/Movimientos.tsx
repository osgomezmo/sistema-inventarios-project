import { useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { Plus, TriangleAlert } from 'lucide-react'
import type { TipoMovimiento, TipoMovimientoManual } from '../api/types'
import { movimientosApi } from '../api/cliente'
import { bodegaPorId, productoPorSku, productos, usuarioPorId } from '../api/mock/maestros'
import { saldosActuales } from '../api/mock/simulacion'
import { useUsuario } from '../auth/Sesion'
import { puedeEditar } from '../auth/permisos'
import { useBodega } from '../contexto/Bodega'
import { useAvisos } from '../contexto/Avisos'
import { BotonEnvio, CantidadMov, Campo, Cargando, Encabezado, ErrorCaja, Paginacion, TipoMov, Vacio, erroresCampo } from '../componentes/ui'
import { cantidad, dinero, fechaHora, nombreTipo, numeroMovimiento, unidad } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'

const TIPOS = Object.keys(nombreTipo) as TipoMovimiento[]

export function Movimientos() {
  const usuario = useUsuario()
  const { idBodega, activas } = useBodega()
  const [params, setParams] = useSearchParams()
  const f = {
    tipo: (params.get('tipo') as TipoMovimiento) || undefined,
    id_bodega: params.has('bodega') ? Number(params.get('bodega')) || undefined : idBodega,
    sku: params.get('sku') || undefined,
    desde: params.get('desde') || undefined,
    hasta: params.get('hasta') || undefined,
    page: Number(params.get('page') ?? 1),
  }
  const c = useConsulta(() => movimientosApi.listar({ ...f, per_page: 20 }), [params.toString(), idBodega])
  const cambiar = (clave: string, valor: string) => {
    const p = new URLSearchParams(params)
    if (valor) p.set(clave, valor); else p.delete(clave)
    if (clave !== 'page') p.delete('page')
    setParams(p)
  }

  return (
    <>
      <Encabezado
        titulo="Movimientos"
        descripcion="Kardex inmutable de entradas, salidas, ajustes y traslados. Nada se edita ni se borra: un error se corrige con otro movimiento."
        acciones={puedeEditar(usuario.rol, 'movimientos') && <Link className="btn btn-pri" to="/movimientos/nuevo"><Plus size={18} aria-hidden />Registrar movimiento</Link>}
      />
      <div className="filtros">
        <div className="campo">
          <label htmlFor="f-bodega">Bodega</label>
          <select id="f-bodega" value={params.has('bodega') ? params.get('bodega')! : String(idBodega)} onChange={(e) => cambiar('bodega', e.target.value || '0')}>
            <option value="0">Todas</option>
            {activas.map((b) => <option key={b.id_bodega} value={b.id_bodega}>{b.codigo} · {b.nombre}</option>)}
          </select>
        </div>
        <div className="campo">
          <label htmlFor="f-tipo">Tipo</label>
          <select id="f-tipo" value={f.tipo ?? ''} onChange={(e) => cambiar('tipo', e.target.value)}>
            <option value="">Todos</option>
            {TIPOS.map((t) => <option key={t} value={t}>{nombreTipo[t]}</option>)}
          </select>
        </div>
        <div className="campo">
          <label htmlFor="f-sku">Producto</label>
          <select id="f-sku" value={f.sku ?? ''} onChange={(e) => cambiar('sku', e.target.value)}>
            <option value="">Todos</option>
            {productos.map((p) => <option key={p.sku} value={p.sku}>{p.sku} · {p.nombre}</option>)}
          </select>
        </div>
        <div className="campo">
          <label htmlFor="f-desde">Desde</label>
          <input id="f-desde" type="date" value={f.desde ?? ''} onChange={(e) => cambiar('desde', e.target.value)} />
        </div>
        <div className="campo">
          <label htmlFor="f-hasta">Hasta</label>
          <input id="f-hasta" type="date" value={f.hasta ?? ''} onChange={(e) => cambiar('hasta', e.target.value)} />
        </div>
      </div>

      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      <div className="tabla-envoltura" style={{ opacity: c.cargando && c.datos ? 0.6 : 1 }}>
        {!c.datos && !c.error && <Cargando filas={10} />}
        {c.datos && (c.datos.data.length === 0 ? <Vacio titulo="Ningún movimiento con estos filtros">Amplía el rango de fechas o quita algún filtro.</Vacio> : (
          <>
            <table className="tabla">
              <thead>
                <tr><th>Documento</th><th>Fecha</th><th>Producto</th><th>Bodega</th><th className="num">Cantidad</th><th className="num">Saldo resultante</th><th className="num">Costo prom.</th><th>Motivo o referencia</th><th>Usuario</th></tr>
              </thead>
              <tbody>
                {c.datos.data.map((m) => {
                  const p = productoPorSku.get(m.sku)!
                  return (
                    <tr key={m.id_movimiento}>
                      <td><span className="doc">{numeroMovimiento(m.id_movimiento)}</span><span className="secundario"><TipoMov tipo={m.tipo} /></span></td>
                      <td className="cifra">{fechaHora(m.fecha)}</td>
                      <td>{p.nombre}<span className="secundario">{m.sku}</span></td>
                      <td>{bodegaPorId.get(m.id_bodega)!.codigo}</td>
                      <td className="num"><CantidadMov m={m} /></td>
                      <td className="num cifra">{cantidad(m.saldo_resultante, p.unidad_medida)}</td>
                      <td className="num cifra">{dinero(m.costo_promedio)}</td>
                      <td>{m.motivo ?? '—'}{m.documento_referencia && <span className="secundario">{m.documento_referencia}</span>}</td>
                      <td>{usuarioPorId.get(m.id_usuario)?.nombre ?? '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <Paginacion meta={c.datos.meta} cambiar={(n) => cambiar('page', String(n))} />
          </>
        ))}
      </div>
    </>
  )
}

const TIPOS_MANUALES: Array<{ tipo: TipoMovimientoManual; texto: string; ayuda: string }> = [
  { tipo: 'SALIDA', texto: 'Salida', ayuda: 'Mercancía que sale a góndola o al cliente, con el documento del POS.' },
  { tipo: 'AJUSTE_NEGATIVO', texto: 'Ajuste negativo', ayuda: 'Merma, daño o diferencia de conteo que baja el saldo.' },
  { tipo: 'AJUSTE_POSITIVO', texto: 'Ajuste positivo', ayuda: 'Diferencia de conteo o inventario inicial que sube el saldo.' },
]

export function NuevoMovimiento() {
  const usuario = useUsuario()
  const { idBodega, activas } = useBodega()
  const navegar = useNavigate()
  const avisar = useAvisos()
  const [tipo, setTipo] = useState<TipoMovimientoManual>('SALIDA')
  const [sku, setSku] = useState('')
  const [bodega, setBodega] = useState(idBodega)
  const [cant, setCant] = useState('')
  const [costo, setCosto] = useState('')
  const [motivo, setMotivo] = useState('')
  const [documento, setDocumento] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const campos = erroresCampo(error)

  const p = productoPorSku.get(sku)
  const saldo = useMemo(() => saldosActuales().find((s) => s.sku === sku && s.id_bodega === bodega), [sku, bodega, enviando])
  const n = Number(cant.replace(',', '.'))
  const resultado = saldo && n > 0 ? (tipo === 'AJUSTE_POSITIVO' ? saldo.cantidad + n : saldo.cantidad - n) : null

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      const m = await movimientosApi.crear({ sku, id_bodega: bodega, tipo, cantidad: n, costo_unitario: costo ? Number(costo) : undefined, motivo, documento_referencia: documento }, usuario.id)
      avisar(`${numeroMovimiento(m.id_movimiento)} registrado: ${nombreTipo[m.tipo].toLowerCase()} de ${cantidad(m.cantidad, p!.unidad_medida)}`, { a: `/kardex?sku=${m.sku}&id_bodega=${m.id_bodega}`, texto: 'Ver kardex' })
      navegar('/movimientos')
    } catch (err) {
      setError(err as Error)
    } finally {
      setEnviando(false)
    }
  }

  if (!puedeEditar(usuario.rol, 'movimientos')) return <Vacio titulo="Tu rol solo puede consultar movimientos" />

  return (
    <>
      <Encabezado migas={<><Link to="/movimientos">Movimientos</Link><span aria-hidden>/</span><span>Nuevo</span></>} titulo="Registrar movimiento" descripcion="Las entradas por compra llegan solas al recibir una orden; aquí se registran salidas y ajustes." />
      <div className="dos-columnas">
        <form className="panel formulario" onSubmit={enviar} noValidate>
          {error && !Object.keys(campos).length && <ErrorCaja error={error} />}
          <fieldset className="campo" style={{ border: 0, padding: 0, margin: 0 }}>
            <legend className="etiqueta" style={{ marginBottom: 6 }}>Tipo de movimiento</legend>
            <div className="opciones-tipo">
              {TIPOS_MANUALES.map((t) => (
                <label key={t.tipo}><input type="radio" name="tipo" value={t.tipo} checked={tipo === t.tipo} onChange={() => setTipo(t.tipo)} />{t.texto}</label>
              ))}
            </div>
            <span className="ayuda">{TIPOS_MANUALES.find((t) => t.tipo === tipo)!.ayuda}</span>
          </fieldset>
          <div className="fila-campos">
            <Campo id="m-sku" etiqueta="Producto" error={campos.sku}>
              <select id="m-sku" value={sku} onChange={(e) => setSku(e.target.value)} required>
                <option value="">Elige un producto</option>
                {productos.filter((x) => x.estado === 'ACTIVO').map((x) => <option key={x.sku} value={x.sku}>{x.sku} · {x.nombre}</option>)}
              </select>
            </Campo>
            <Campo id="m-bodega" etiqueta="Bodega">
              <select id="m-bodega" value={bodega} onChange={(e) => setBodega(Number(e.target.value))}>
                {activas.map((b) => <option key={b.id_bodega} value={b.id_bodega}>{b.codigo} · {b.nombre}</option>)}
              </select>
            </Campo>
          </div>
          <div className="fila-campos">
            <Campo id="m-cant" etiqueta={`Cantidad${p ? ` (${unidad(p.unidad_medida)})` : ''}`} error={campos.cantidad} ayuda={p && p.unidad_medida !== 'UNIDAD' ? 'Hasta tres decimales.' : undefined}>
              <input id="m-cant" inputMode="decimal" value={cant} onChange={(e) => setCant(e.target.value)} />
            </Campo>
            {tipo === 'AJUSTE_POSITIVO' && (
              <Campo id="m-costo" etiqueta="Costo unitario" opcional ayuda="Si lo dejas vacío se usa el costo promedio vigente.">
                <input id="m-costo" inputMode="decimal" value={costo} onChange={(e) => setCosto(e.target.value)} />
              </Campo>
            )}
            {tipo === 'SALIDA' && (
              <Campo id="m-doc" etiqueta="Documento del POS" error={campos.documento_referencia} ayuda="Por ejemplo, el cierre de caja o la factura.">
                <input id="m-doc" value={documento} onChange={(e) => setDocumento(e.target.value)} placeholder="Cierre POS 29/10 turno 2" />
              </Campo>
            )}
          </div>
          <Campo id="m-motivo" etiqueta="Motivo" opcional={tipo === 'SALIDA'} error={campos.motivo}>
            <textarea id="m-motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder={tipo === 'SALIDA' ? 'Opcional' : 'Merma: producto en mal estado'} />
          </Campo>
          <div className="acciones-separadas">
            <BotonEnvio enviando={enviando}>Registrar movimiento</BotonEnvio>
            <Link className="btn btn-fantasma" to="/movimientos">Cancelar</Link>
          </div>
        </form>

        <aside className="panel" aria-live="polite">
          <h2>Saldo en {bodegaPorId.get(bodega)!.codigo}</h2>
          {!p ? <p>Elige un producto para ver su saldo actual y cómo quedará.</p> : (
            <>
              <div className="resumen-cifras">
                <div><span>Actual</span><strong>{cantidad(saldo?.cantidad ?? 0, p.unidad_medida)}</strong></div>
                <div><span>Quedará</span><strong>{resultado === null ? '—' : cantidad(Math.max(resultado, 0), p.unidad_medida)}</strong></div>
              </div>
              <dl className="datos">
                <dt>Stock mínimo</dt><dd>{cantidad(p.stock_minimo, p.unidad_medida)}</dd>
                <dt>Costo promedio</dt><dd>{dinero(saldo?.costo_promedio ?? 0)}</dd>
              </dl>
              {resultado !== null && resultado < 0 && (
                <div className="aviso aviso-error" style={{ marginTop: 16 }}><TriangleAlert size={20} aria-hidden /><div><strong>No hay saldo suficiente</strong><p>Ninguna salida puede dejar el saldo en negativo.</p></div></div>
              )}
              {resultado !== null && resultado >= 0 && resultado <= p.stock_minimo && (
                <div className="aviso aviso-alerta" style={{ marginTop: 16 }}><TriangleAlert size={20} aria-hidden /><div><strong>Quedará en stock bajo</strong><p>Se avisará a Compras y a los jefes de bodega.</p></div></div>
              )}
            </>
          )}
        </aside>
      </div>
    </>
  )
}
