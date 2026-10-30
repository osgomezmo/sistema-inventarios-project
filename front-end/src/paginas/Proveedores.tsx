import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { Mail, Phone, Plus } from 'lucide-react'
import { ordenesApi, proveedoresApi } from '../api/cliente'
import { productoPorSku } from '../api/mock/maestros'
import { useUsuario } from '../auth/Sesion'
import { puedeEditar } from '../auth/permisos'
import { Cargando, Encabezado, ErrorCaja, EtiquetaEstado, EtiquetaOrden, Vacio } from '../componentes/ui'
import { dinero, fecha } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'
import { useAvisos } from '../contexto/Avisos'
import { AltaProveedor } from './Altas'

export function Proveedores() {
  const usuario = useUsuario()
  const avisar = useAvisos()
  const [alta, setAlta] = useState(false)
  const [q, setQ] = useState('')
  const [estado, setEstado] = useState<'' | 'ACTIVO' | 'INACTIVO'>('')
  const c = useConsulta(() => proveedoresApi.listar({ q, estado: estado || undefined }), [q, estado])
  return (
    <>
      <Encabezado
        titulo="Proveedores"
        descripcion="Un proveedor inactivo no puede usarse en órdenes nuevas."
        acciones={puedeEditar(usuario.rol, 'proveedores') && <button type="button" className="btn btn-pri" aria-expanded={alta} onClick={() => setAlta(!alta)}><Plus size={18} aria-hidden />Nuevo proveedor</button>}
      />
      {alta && <AltaProveedor listo={(t) => { avisar(t); setAlta(false); c.recargar() }} cancelar={() => setAlta(false)} />}
      <div className="filtros">
        <div className="campo ancho"><label htmlFor="p-q">Buscar</label><input id="p-q" type="search" placeholder="NIT o razón social" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <div className="campo">
          <label htmlFor="p-estado">Estado</label>
          <select id="p-estado" value={estado} onChange={(e) => setEstado(e.target.value as typeof estado)}>
            <option value="">Todos</option><option value="ACTIVO">Activos</option><option value="INACTIVO">Inactivos</option>
          </select>
        </div>
      </div>
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      <div className="tabla-envoltura">
        {!c.datos && !c.error && <Cargando />}
        {c.datos && (c.datos.data.length === 0 ? <Vacio titulo="Ningún proveedor coincide">Prueba con otra parte del NIT o del nombre.</Vacio> : (
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
        ))}
      </div>
    </>
  )
}

export function ProveedorDetalle() {
  const { id = '' } = useParams()
  const c = useConsulta(() => Promise.all([proveedoresApi.obtener(Number(id)), proveedoresApi.productos(Number(id)), ordenesApi.listar({ id_proveedor: Number(id) })]), [id])
  if (c.error) return <ErrorCaja error={c.error} reintentar={c.recargar} />
  if (!c.datos) return <div className="panel"><Cargando /></div>
  const [p, suministra, ordenes] = c.datos
  return (
    <>
      <Encabezado migas={<><Link to="/proveedores">Proveedores</Link><span aria-hidden>/</span><span>{p.nit}</span></>} titulo={p.razon_social} descripcion={<>NIT {p.nit} · {p.direccion}</>} acciones={<EtiquetaEstado estado={p.estado} />} />
      <div className="dos-columnas">
        <div className="pila">
          <section className="tabla-envoltura" aria-labelledby="t-sum">
            <div className="panel-titulo" style={{ padding: '16px 16px 0' }}><h2 id="t-sum">Productos que suministra</h2></div>
            {suministra.length === 0 ? <Vacio titulo="Sin productos asociados" /> : (
              <table className="tabla">
                <thead><tr><th>Producto</th><th className="num">Precio de compra</th><th className="num">Días de entrega</th><th>Estado</th></tr></thead>
                <tbody>
                  {suministra.map((s) => (
                    <tr key={s.sku}><td>{productoPorSku.get(s.sku)!.nombre}<span className="secundario">{s.sku}</span></td><td className="num cifra">{dinero(s.precio_compra)}</td><td className="num cifra">{s.dias_entrega}</td><td><EtiquetaEstado estado={s.estado} /></td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
          <section className="tabla-envoltura" aria-labelledby="t-oc">
            <div className="panel-titulo" style={{ padding: '16px 16px 0' }}><h2 id="t-oc">Órdenes de compra</h2></div>
            {ordenes.data.length === 0 ? <Vacio titulo="Sin órdenes con este proveedor" /> : (
              <table className="tabla">
                <thead><tr><th>Orden</th><th>Estado</th><th className="num">Total</th><th>Creada</th></tr></thead>
                <tbody>
                  {ordenes.data.map((o) => <tr key={o.id_orden}><td><Link className="doc" to={`/ordenes-compra/${o.id_orden}`}>{o.numero}</Link></td><td><EtiquetaOrden estado={o.estado} /></td><td className="num cifra">{dinero(o.total)}</td><td className="cifra">{fecha(o.fecha_creacion)}</td></tr>)}
                </tbody>
              </table>
            )}
          </section>
        </div>
        <aside className="panel">
          <h2>Contactos</h2>
          {p.contactos.length === 0 ? <p>Sin contactos registrados.</p> : p.contactos.map((ct) => (
            <div key={ct.id_contacto} style={{ display: 'grid', gap: 4, padding: '12px 0', borderBottom: '1px solid var(--linea)' }}>
              <strong style={{ fontSize: 'var(--t-l)' }}>{ct.nombre}</strong>
              <span style={{ color: 'var(--tinta-2)' }}>{ct.cargo}</span>
              <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}><Phone size={16} aria-hidden />{ct.telefono}</span>
              <a href={`mailto:${ct.email}`} style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}><Mail size={16} aria-hidden />{ct.email}</a>
            </div>
          ))}
          <dl className="datos" style={{ marginTop: 16 }}>
            <dt>Teléfono</dt><dd>{p.telefono}</dd>
            <dt>Correo</dt><dd>{p.email}</dd>
          </dl>
        </aside>
      </div>
    </>
  )
}
