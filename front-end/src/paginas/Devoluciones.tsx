import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { Plus } from 'lucide-react'
import { devolucionesClienteApi, devolucionesProveedorApi } from '../api/cliente'
import { bodega as bodegaDe, nombreUsuario, producto, productoPorSku, productos, proveedor } from '../api/maestros'
import { useUsuario } from '../auth/Sesion'
import { puedeEditar, puedeVer } from '../auth/permisos'
import { useAvisos } from '../contexto/Avisos'
import { useBodega } from '../contexto/Bodega'
import { useMaestros } from '../contexto/Maestros'
import { BotonEnvio, Campo, Cargando, Encabezado, ErrorCaja, Paginacion, Vacio, erroresCampo } from '../componentes/ui'
import { cantidad, fechaHora, numeroMovimiento, unidad } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'
import { aNumero, decimalesPorUnidad, reglas, useValidacion, validar } from '../lib/validacion'

export function Devoluciones() {
  const usuario = useUsuario()
  useMaestros()
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
  const [page, setPage] = useState(1)
  const c = useConsulta(() => devolucionesClienteApi.listar({ page }), [page])
  return (
    <div className="tabla-envoltura" role="tabpanel">
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      {!c.datos && !c.error && <Cargando />}
      {c.datos && (c.datos.data.length === 0 ? <Vacio titulo="Sin devoluciones de clientes" /> : (
        <>
          <table className="tabla">
            <thead><tr><th>Movimiento</th><th>Fecha</th><th>Factura POS</th><th>Producto</th><th>Bodega</th><th className="num">Cantidad</th><th>Motivo</th><th>Registró</th></tr></thead>
            <tbody>
              {c.datos.data.map((m) => {
                const p = producto(m.sku)
                return (
                  <tr key={m.id_movimiento}>
                    <td className="doc">{numeroMovimiento(m.id_movimiento)}</td>
                    <td className="cifra">{fechaHora(m.fecha)}</td>
                    <td>{m.documento_referencia}</td>
                    <td>{p.nombre}<span className="secundario">{m.sku}</span></td>
                    <td>{bodegaDe(m.id_bodega).codigo}</td>
                    <td className="num cifra mas">+{cantidad(m.cantidad, p.unidad_medida)}</td>
                    <td>{m.motivo}</td>
                    <td>{nombreUsuario(m.id_usuario)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <Paginacion meta={c.datos.meta} cambiar={setPage} />
        </>
      ))}
    </div>
  )
}

function AProveedores() {
  const [page, setPage] = useState(1)
  const c = useConsulta(() => devolucionesProveedorApi.listar({ page }), [page])
  return (
    <div className="tabla-envoltura" role="tabpanel">
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      {!c.datos && !c.error && <Cargando />}
      {c.datos && (c.datos.data.length === 0 ? <Vacio titulo="Sin devoluciones a proveedores">Se registran desde una orden de compra recibida.</Vacio> : (
        <>
          <table className="tabla">
            <thead><tr><th>Orden</th><th>Fecha</th><th>Proveedor</th><th>Productos</th><th>Motivo</th><th>Registró</th></tr></thead>
            <tbody>
              {c.datos.data.map((d) => (
                <tr key={d.id_devolucion}>
                  <td><Link className="doc" to={`/ordenes-compra/${d.id_orden}`}>{d.numero_orden ?? `Orden ${d.id_orden}`}</Link></td>
                  <td className="cifra">{fechaHora(d.fecha)}</td>
                  <td>{proveedor(d.id_proveedor).razon_social}</td>
                  <td>{d.items.map((i) => {
                    const p = i.sku ? producto(i.sku) : null
                    return <span key={i.id_detalle} style={{ display: 'block' }}>{p ? `${p.nombre}: ${cantidad(i.cantidad, p.unidad_medida)}` : `Renglón ${i.id_detalle}: ${i.cantidad}`}</span>
                  })}</td>
                  <td>{d.motivo}</td>
                  <td>{nombreUsuario(d.id_usuario)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Paginacion meta={c.datos.meta} cambiar={setPage} />
        </>
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
  const p = productoPorSku.get(sku)

  const v = useValidacion(validar({
    factura_pos: [reglas.requerido(factura, 'Indica la factura del POS.'), reglas.facturaPos(factura)],
    sku: [reglas.requerido(sku, 'Elige el producto que devuelve el cliente.')],
    cantidad: [reglas.numero(cant, { requerido: true, mensajeVacio: 'Escribe la cantidad devuelta.', decimales: p ? decimalesPorUnidad(p.unidad_medida) : 3, mayorQueCero: true, max: 10000, mensajeMax: 'Revisa la cantidad: parece demasiado alta para una devolución.' })],
    motivo: [reglas.requerido(motivo, 'Indica el motivo de la devolución.'), reglas.largo(motivo, 5, 200)],
  }))
  const campos = { ...erroresCampo(error), ...v.visibles }

  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!v.comprobar(e.currentTarget)) return
    setEnviando(true)
    setError(null)
    try {
      const m = await devolucionesClienteApi.crear({ sku, id_bodega: bodega, cantidad: aNumero(cant) ?? 0, factura_pos: factura.trim().toUpperCase(), motivo: motivo.trim() })
      avisar(`Devolución registrada como ${numeroMovimiento(m.id_movimiento)}: reingresan ${cantidad(m.cantidad, producto(m.sku).unidad_medida)}`)
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
      <form className="panel formulario" onSubmit={enviar} onBlur={v.alSalir} noValidate>
        {error && !Object.keys(erroresCampo(error)).length && <ErrorCaja error={error} />}
        <div className="fila-campos">
          <Campo id="d-factura" etiqueta="Factura del POS" error={campos.factura_pos}>
            <input id="d-factura" name="factura_pos" maxLength={30} value={factura} onChange={(e) => setFactura(e.target.value)} placeholder="FV-POS-0019802" />
          </Campo>
          <Campo id="d-bodega" etiqueta="Bodega que recibe">
            <select id="d-bodega" value={bodega} onChange={(e) => setBodega(Number(e.target.value))}>
              {activas.map((b) => <option key={b.id_bodega} value={b.id_bodega}>{b.codigo} · {b.nombre}</option>)}
            </select>
          </Campo>
        </div>
        <div className="fila-campos">
          <Campo id="d-sku" etiqueta="Producto" error={campos.sku}>
            <select id="d-sku" name="sku" value={sku} onChange={(e) => setSku(e.target.value)}>
              <option value="">Elige un producto</option>
              {productos.filter((x) => x.estado === 'ACTIVO').map((x) => <option key={x.sku} value={x.sku}>{x.sku} · {x.nombre}</option>)}
            </select>
          </Campo>
          <Campo id="d-cant" etiqueta={`Cantidad${p ? ` (${unidad(p.unidad_medida)})` : ''}`} error={campos.cantidad}>
            <input id="d-cant" name="cantidad" inputMode="decimal" maxLength={14} value={cant} onChange={(e) => setCant(e.target.value)} />
          </Campo>
        </div>
        <Campo id="d-motivo" etiqueta="Motivo" error={campos.motivo} ayuda="Entre 5 y 200 caracteres.">
          <textarea id="d-motivo" name="motivo" maxLength={200} value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Producto defectuoso" />
        </Campo>
        <div className="acciones-separadas">
          <BotonEnvio enviando={enviando}>Registrar devolución</BotonEnvio>
          <Link className="btn btn-fantasma" to="/devoluciones">Cancelar</Link>
        </div>
      </form>
    </>
  )
}
