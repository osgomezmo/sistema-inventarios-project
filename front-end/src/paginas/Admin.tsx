import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Check, Minus, Plus } from 'lucide-react'
import { auth, buscarTodo, usuariosApi } from '../api/cliente'
import { bodegaPorId, productoPorSku, proveedorPorId } from '../api/mock/maestros'
import { useUsuario } from '../auth/Sesion'
import { acceso, nombreRol, type Operacion } from '../auth/permisos'
import { useAvisos } from '../contexto/Avisos'
import { BotonEnvio, Campo, Cargando, Encabezado, ErrorCaja, EtiquetaEstado, EtiquetaOrden, TipoMov, Vacio, erroresCampo } from '../componentes/ui'
import { dinero, fechaHora, numeroMovimiento } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'
import type { Rol } from '../api/types'
import { AltaUsuario } from './Altas'

const ROLES: Rol[] = ['ADMINISTRADOR', 'JEFE_BODEGA', 'COMPRAS', 'GERENTE']
const OPERACIONES: Array<[Operacion, string]> = [
  ['usuarios', 'Usuarios y roles'], ['catalogo', 'Productos y categorías'], ['bodegas', 'Bodegas'], ['stock', 'Consultar saldos'],
  ['movimientos', 'Movimientos, ajustes y traslados'], ['devolucionCliente', 'Devolución de cliente'], ['proveedores', 'Proveedores y sus productos'],
  ['ordenes', 'Crear y editar órdenes de compra'], ['aprobarOrdenes', 'Aprobar y anular órdenes'], ['recibirMercancia', 'Recibir mercancía'],
  ['devolucionProveedor', 'Devolución a proveedor'], ['reportes', 'Reportes y dashboard'],
]

export function Usuarios() {
  const yo = useUsuario()
  const avisar = useAvisos()
  const c = useConsulta(() => usuariosApi.listar(), [])
  const [alta, setAlta] = useState(false)
  async function alternar(id: number, estado: 'ACTIVO' | 'INACTIVO') {
    const u = await usuariosApi.cambiarEstado(id, estado)
    avisar(estado === 'INACTIVO' ? `${u.nombre} quedó inactivo y se revocaron sus tokens` : `${u.nombre} quedó activo`)
    c.recargar()
  }
  return (
    <>
      <Encabezado titulo="Usuarios y roles" descripcion="Los usuarios, roles y tokens viven en el API Gateway. Inactivar a un usuario revoca sus sesiones abiertas."
        acciones={<button type="button" className="btn btn-pri" aria-expanded={alta} onClick={() => setAlta(!alta)}><Plus size={18} aria-hidden />Nuevo usuario</button>} />
      {alta && <AltaUsuario listo={(t) => { avisar(t); setAlta(false); c.recargar() }} cancelar={() => setAlta(false)} />}
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      <div className="pila">
        <div className="tabla-envoltura">
          {!c.datos && !c.error && <Cargando />}
          {c.datos && (
            <table className="tabla">
              <thead><tr><th>Usuario</th><th>Rol</th><th>Último acceso</th><th>Estado</th><th><span className="solo-lector">Acciones</span></th></tr></thead>
              <tbody>
                {c.datos.data.map((u) => (
                  <tr key={u.id}>
                    <td><strong>{u.nombre}</strong><span className="secundario">{u.email}</span></td>
                    <td>{nombreRol[u.rol]}</td>
                    <td className="cifra">{u.ultimo_acceso ? fechaHora(u.ultimo_acceso) : '—'}</td>
                    <td><EtiquetaEstado estado={u.estado} /></td>
                    <td>{u.id !== yo.id && (u.estado === 'ACTIVO'
                      ? <button type="button" className="btn btn-sm btn-fantasma" onClick={() => alternar(u.id, 'INACTIVO')}>Inactivar</button>
                      : <button type="button" className="btn btn-sm" onClick={() => alternar(u.id, 'ACTIVO')}>Activar</button>)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <section className="tabla-envoltura" aria-labelledby="t-matriz">
          <div className="panel-titulo" style={{ padding: '16px 16px 0' }}><h2 id="t-matriz">Permisos por rol</h2></div>
          <table className="tabla">
            <thead><tr><th>Operación</th>{ROLES.map((r) => <th key={r}>{nombreRol[r]}</th>)}</tr></thead>
            <tbody>
              {OPERACIONES.map(([op, texto]) => (
                <tr key={op}>
                  <td>{texto}</td>
                  {ROLES.map((r) => {
                    const a = acceso(r, op)
                    return <td key={r}>{a === 'editar' ? <span className="tag"><Check size={14} aria-hidden />Sí</span> : a === 'ver' ? <span className="tag tag-info">Ver</span> : <span className="tag tag-inactivo" aria-label="Sin acceso"><Minus size={14} aria-hidden /></span>}</td>
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </>
  )
}

export function Perfil() {
  const usuario = useUsuario()
  const avisar = useAvisos()
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const campos = erroresCampo(error)
  async function enviar(e: FormEvent) {
    e.preventDefault()
    setEnviando(true)
    setError(null)
    try { await auth.cambiarPassword(actual, nueva); avisar('Contraseña actualizada'); setActual(''); setNueva('') } catch (err) { setError(err as Error) } finally { setEnviando(false) }
  }
  return (
    <>
      <Encabezado titulo="Cambiar contraseña" descripcion={`${usuario.nombre} · ${usuario.email}`} />
      <form className="panel formulario" onSubmit={enviar} noValidate>
        <Campo id="pw-actual" etiqueta="Contraseña actual" error={campos.password_actual}><input id="pw-actual" type="password" autoComplete="current-password" value={actual} onChange={(e) => setActual(e.target.value)} /></Campo>
        <Campo id="pw-nueva" etiqueta="Contraseña nueva" error={campos.password_nueva} ayuda="Mínimo 8 caracteres."><input id="pw-nueva" type="password" autoComplete="new-password" value={nueva} onChange={(e) => setNueva(e.target.value)} /></Campo>
        <div className="acciones-separadas"><BotonEnvio enviando={enviando}>Guardar contraseña</BotonEnvio></div>
      </form>
    </>
  )
}

export function Buscar() {
  const [params] = useSearchParams()
  const q = params.get('q') ?? ''
  const c = useConsulta(() => buscarTodo(q), [q])
  const total = c.datos ? c.datos.productos.length + c.datos.ordenes.length + c.datos.movimientos.length + c.datos.proveedores.length : 0
  return (
    <>
      <Encabezado titulo={`Resultados para «${q}»`} descripcion="Busca por SKU, nombre de producto, número de orden (OC-2026-0015), movimiento (MOV-004812), factura del POS o proveedor." />
      {c.error && <ErrorCaja error={c.error} />}
      {!c.datos && !c.error && <div className="panel"><Cargando /></div>}
      {c.datos && (total === 0 ? <div className="panel"><Vacio titulo="Sin resultados">Revisa el número del documento o prueba con parte del nombre.</Vacio></div> : (
        <div className="pila">
          {c.datos.productos.length > 0 && (
            <section className="tabla-envoltura"><div className="panel-titulo" style={{ padding: '16px 16px 0' }}><h2>Productos</h2></div>
              <table className="tabla"><tbody>{c.datos.productos.map((p) => <tr key={p.sku}><td><Link to={`/stock/${p.sku}`}><strong>{p.nombre}</strong></Link><span className="secundario">{p.sku} · {p.marca}</span></td><td className="num cifra">{dinero(p.precio_venta)}</td><td><EtiquetaEstado estado={p.estado} /></td></tr>)}</tbody></table>
            </section>
          )}
          {c.datos.ordenes.length > 0 && (
            <section className="tabla-envoltura"><div className="panel-titulo" style={{ padding: '16px 16px 0' }}><h2>Órdenes de compra</h2></div>
              <table className="tabla"><tbody>{c.datos.ordenes.map((o) => <tr key={o.id_orden}><td><Link className="doc" to={`/ordenes-compra/${o.id_orden}`}>{o.numero}</Link></td><td>{proveedorPorId.get(o.id_proveedor)!.razon_social}</td><td><EtiquetaOrden estado={o.estado} /></td><td className="num cifra">{dinero(o.total)}</td></tr>)}</tbody></table>
            </section>
          )}
          {c.datos.movimientos.length > 0 && (
            <section className="tabla-envoltura"><div className="panel-titulo" style={{ padding: '16px 16px 0' }}><h2>Movimientos</h2></div>
              <table className="tabla"><tbody>{c.datos.movimientos.map((m) => <tr key={m.id_movimiento}><td><Link className="doc" to={`/kardex?sku=${m.sku}&id_bodega=${m.id_bodega}`}>{numeroMovimiento(m.id_movimiento)}</Link><span className="secundario"><TipoMov tipo={m.tipo} /></span></td><td>{productoPorSku.get(m.sku)!.nombre}</td><td>{bodegaPorId.get(m.id_bodega)!.codigo}</td><td>{m.documento_referencia}</td><td className="cifra">{fechaHora(m.fecha)}</td></tr>)}</tbody></table>
            </section>
          )}
          {c.datos.proveedores.length > 0 && (
            <section className="tabla-envoltura"><div className="panel-titulo" style={{ padding: '16px 16px 0' }}><h2>Proveedores</h2></div>
              <table className="tabla"><tbody>{c.datos.proveedores.map((p) => <tr key={p.id_proveedor}><td><Link to={`/proveedores/${p.id_proveedor}`}><strong>{p.razon_social}</strong></Link></td><td className="cifra">{p.nit}</td><td><EtiquetaEstado estado={p.estado} /></td></tr>)}</tbody></table>
            </section>
          )}
        </div>
      ))}
    </>
  )
}
