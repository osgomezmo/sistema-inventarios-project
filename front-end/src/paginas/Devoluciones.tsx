import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { Plus } from 'lucide-react'
import { devolucionesClienteApi, devolucionesProveedorApi } from '../api/cliente'
import { bodegaPorId, productoPorSku, productos, proveedorPorId, usuarioPorId } from '../api/mock/maestros'
import { ordenes } from '../api/mock/simulacion'
import { useUsuario } from '../auth/Sesion'
import { puedeEditar, puedeVer } from '../auth/permisos'
import { useAvisos } from '../contexto/Avisos'
import { useBodega } from '../contexto/Bodega'
import { BotonEnvio, Campo, Cargando, Encabezado, ErrorCaja, Vacio, erroresCampo } from '../componentes/ui'
import { cantidad, fechaHora, numeroMovimiento, unidad } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'

export function Devoluciones() {
  const usuario = useUsuario()
  const [params, setParams] = useSearchParams()
  const verClientes = puedeVer(usuario.rol, 'devolucionCliente')
  const verProveedores = puedeVer(usuario.rol, 'devolucionProveedor')
  const pestana = params.get('de') ?? (verClientes ? 'clientes' : 'proveedores')

  return (
    <>
      <Encabezado
        titulo="Devoluciones"
        descripcion="Las de clientes reingresan al stock con la factura del POS; las de proveedores salen del stock y se registran desde la orden de compra recibida."
        acciones={pestana === 'clientes' && puedeEditar(usuario.rol, 'devolucionCliente') && <Link className="btn btn-pri" to="/devoluciones/cliente/nueva"><Plus size={18} aria-hidden />Devolución de cliente</Link>}
      />
      <div className="pestanas" role="tablist">
        {verClientes && <button type="button" role="tab" aria-selected={pestana === 'clientes'} onClick={() => setParams({ de: 'clientes' })}>De clientes</button>}
        {verProveedores && <button type="button" role="tab" aria-selected={pestana === 'proveedores'} onClick={() => setParams({ de: 'proveedores' })}>A proveedores</button>}
      </div>
      {pestana === 'clientes' && verClientes ? <DeClientes /> : <AProveedores />}
    </>
  )
}

function DeClientes() {
  const c = useConsulta(() => devolucionesClienteApi.listar(), [])
  return (
    <div className="tabla-envoltura" role="tabpanel">
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      {!c.datos && !c.error && <Cargando />}
      {c.datos && (c.datos.data.length === 0 ? <Vacio titulo="Sin devoluciones de clientes" /> : (
        <table className="tabla">
          <thead><tr><th>Movimiento</th><th>Fecha</th><th>Factura POS</th><th>Producto</th><th>Bodega</th><th className="num">Cantidad</th><th>Motivo</th><th>Registró</th></tr></thead>
          <tbody>
            {c.datos.data.map((m) => {
              const p = productoPorSku.get(m.sku)!
              return (
                <tr key={m.id_movimiento}>
                  <td className="doc">{numeroMovimiento(m.id_movimiento)}</td>
                  <td className="cifra">{fechaHora(m.fecha)}</td>
                  <td>{m.documento_referencia}</td>
                  <td>{p.nombre}<span className="secundario">{m.sku}</span></td>
                  <td>{bodegaPorId.get(m.id_bodega)!.codigo}</td>
                  <td className="num cifra mas">+{cantidad(m.cantidad, p.unidad_medida)}</td>
                  <td>{m.motivo}</td>
                  <td>{usuarioPorId.get(m.id_usuario)?.nombre}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      ))}
    </div>
  )
}

function AProveedores() {
  const c = useConsulta(() => devolucionesProveedorApi.listar(), [])
  return (
    <div className="tabla-envoltura" role="tabpanel">
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      {!c.datos && !c.error && <Cargando />}
      {c.datos && (c.datos.data.length === 0 ? <Vacio titulo="Sin devoluciones a proveedores">Se registran desde una orden de compra recibida.</Vacio> : (
        <table className="tabla">
          <thead><tr><th>Orden</th><th>Fecha</th><th>Proveedor</th><th>Productos</th><th>Motivo</th><th>Registró</th></tr></thead>
          <tbody>
            {c.datos.data.map((d) => {
              const o = ordenes.find((x) => x.id_orden === d.id_orden)!
              return (
                <tr key={d.id_devolucion}>
                  <td><Link className="doc" to={`/ordenes-compra/${o.id_orden}`}>{o.numero}</Link></td>
                  <td className="cifra">{fechaHora(d.fecha)}</td>
                  <td>{proveedorPorId.get(d.id_proveedor)!.razon_social}</td>
                  <td>{d.items.map((i) => {
                    const det = o.items.find((x) => x.id_detalle === i.id_detalle)!
                    const p = productoPorSku.get(det.sku)!
                    return <span key={i.id_detalle} style={{ display: 'block' }}>{p.nombre}: {cantidad(i.cantidad, p.unidad_medida)}</span>
                  })}</td>
                  <td>{d.motivo}</td>
                  <td>{usuarioPorId.get(d.id_usuario)?.nombre}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      ))}
    </div>
  )
}

export function NuevaDevolucionCliente() {
  const usuario = useUsuario()
  const { idBodega, activas } = useBodega()
  const navegar = useNavigate()
  const avisar = useAvisos()
  const [sku, setSku] = useState('')
  const [bodega, setBodega] = useState(idBodega)
  const [cant, setCant] = useState('')
  const [factura, setFactura] = useState('')
  const [motivo, setMotivo] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const campos = erroresCampo(error)
  const p = productoPorSku.get(sku)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      const m = await devolucionesClienteApi.crear({ sku, id_bodega: bodega, cantidad: Number(cant.replace(',', '.')), factura_pos: factura, motivo }, usuario.id)
      avisar(`Devolución registrada como ${numeroMovimiento(m.id_movimiento)}: reingresan ${cantidad(m.cantidad, p!.unidad_medida)}`)
      navegar('/devoluciones?de=clientes')
    } catch (err) {
      setError(err as Error)
    } finally {
      setEnviando(false)
    }
  }

  if (!puedeEditar(usuario.rol, 'devolucionCliente')) return <Vacio titulo="Tu rol solo puede consultar devoluciones" />

  return (
    <>
      <Encabezado migas={<><Link to="/devoluciones">Devoluciones</Link><span aria-hidden>/</span><span>De cliente</span></>} titulo="Devolución de cliente" descripcion="El producto reingresa al saldo de la bodega con referencia a la factura del POS." />
      <form className="panel formulario" onSubmit={enviar} noValidate>
        {error && !Object.keys(campos).length && <ErrorCaja error={error} />}
        <div className="fila-campos">
          <Campo id="d-factura" etiqueta="Factura del POS" error={campos.factura_pos}>
            <input id="d-factura" value={factura} onChange={(e) => setFactura(e.target.value)} placeholder="FV-POS-0019802" />
          </Campo>
          <Campo id="d-bodega" etiqueta="Bodega que recibe">
            <select id="d-bodega" value={bodega} onChange={(e) => setBodega(Number(e.target.value))}>
              {activas.map((b) => <option key={b.id_bodega} value={b.id_bodega}>{b.codigo} · {b.nombre}</option>)}
            </select>
          </Campo>
        </div>
        <div className="fila-campos">
          <Campo id="d-sku" etiqueta="Producto" error={campos.sku}>
            <select id="d-sku" value={sku} onChange={(e) => setSku(e.target.value)}>
              <option value="">Elige un producto</option>
              {productos.filter((x) => x.estado === 'ACTIVO').map((x) => <option key={x.sku} value={x.sku}>{x.sku} · {x.nombre}</option>)}
            </select>
          </Campo>
          <Campo id="d-cant" etiqueta={`Cantidad${p ? ` (${unidad(p.unidad_medida)})` : ''}`} error={campos.cantidad}>
            <input id="d-cant" inputMode="decimal" value={cant} onChange={(e) => setCant(e.target.value)} />
          </Campo>
        </div>
        <Campo id="d-motivo" etiqueta="Motivo" error={campos.motivo}>
          <textarea id="d-motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Producto defectuoso" />
        </Campo>
        <div className="acciones-separadas">
          <BotonEnvio enviando={enviando}>Registrar devolución</BotonEnvio>
          <Link className="btn btn-fantasma" to="/devoluciones">Cancelar</Link>
        </div>
      </form>
    </>
  )
}
