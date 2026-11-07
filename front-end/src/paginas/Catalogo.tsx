import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { AltaBodega, AltaCategoria, AltaProducto } from './Altas'
import { Boxes, Plus } from 'lucide-react'
import { ApiError, bodegasApi, categoriasApi, productosApi, stockApi } from '../api/cliente'
import { categoriaPorId, categoriaRaiz, productos as todosProductos } from '../api/mock/maestros'
import { useUsuario } from '../auth/Sesion'
import { puedeEditar } from '../auth/permisos'
import { useAvisos } from '../contexto/Avisos'
import { useBodega } from '../contexto/Bodega'
import { Cargando, Encabezado, ErrorCaja, EtiquetaEstado, Paginacion, Vacio } from '../componentes/ui'
import { cantidad, dinero, dineroCorto, unidad } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'

export function Productos() {
  const usuario = useUsuario()
  const avisar = useAvisos()
  const [params, setParams] = useSearchParams()
  const f = {
    q: params.get('q') ?? '',
    id_categoria: Number(params.get('categoria')) || undefined,
    estado: (params.get('estado') as 'ACTIVO' | 'INACTIVO') || undefined,
    precio_min: params.get('min') ? Number(params.get('min')) : undefined,
    precio_max: params.get('max') ? Number(params.get('max')) : undefined,
    page: Number(params.get('page') ?? 1),
  }
  const c = useConsulta(() => productosApi.listar({ ...f, per_page: 15 }), [params.toString()])
  const cats = useConsulta(() => categoriasApi.listar({ estado: 'ACTIVO' }), [])
  const admin = puedeEditar(usuario.rol, 'catalogo')
  const [alta, setAlta] = useState(false)
  const cambiar = (k: string, v: string) => { const n = new URLSearchParams(params); if (v) n.set(k, v); else n.delete(k); if (k !== 'page') n.delete('page'); setParams(n) }

  async function alternar(id: number, estado: 'ACTIVO' | 'INACTIVO') {
    try {
      const p = await productosApi.cambiarEstado(id, estado)
      avisar(`${p.sku} ${estado === 'ACTIVO' ? 'activado' : 'inactivado'}`)
      c.recargar()
    } catch (e) {
      if (e instanceof ApiError) avisar(e.message)
    }
  }

  return (
    <>
      <Encabezado
        titulo="Productos"
        descripcion="Un producto con movimientos no se elimina: se inactiva y conserva su historia."
        acciones={admin && <button type="button" className="btn btn-pri" aria-expanded={alta} onClick={() => setAlta(!alta)}><Plus size={18} aria-hidden />Nuevo producto</button>}
      />
      {alta && <AltaProducto listo={(t) => { avisar(t); setAlta(false); c.recargar() }} cancelar={() => setAlta(false)} />}
      <div className="filtros">
        <div className="campo ancho"><label htmlFor="pr-q">Buscar</label><input id="pr-q" type="search" placeholder="SKU o nombre" value={f.q} onChange={(e) => cambiar('q', e.target.value)} /></div>
        <div className="campo">
          <label htmlFor="pr-cat">Categoría</label>
          <select id="pr-cat" value={f.id_categoria ?? ''} onChange={(e) => cambiar('categoria', e.target.value)}>
            <option value="">Todas</option>
            {(cats.datos ?? []).map((cat) => <option key={cat.id_categoria} value={cat.id_categoria}>{cat.nombre}</option>)}
          </select>
        </div>
        <div className="campo">
          <label htmlFor="pr-estado">Estado</label>
          <select id="pr-estado" value={f.estado ?? ''} onChange={(e) => cambiar('estado', e.target.value)}>
            <option value="">Todos</option><option value="ACTIVO">Activos</option><option value="INACTIVO">Inactivos</option>
          </select>
        </div>
        <div className="campo" style={{ width: 150 }}><label htmlFor="pr-min">Precio desde</label><input id="pr-min" inputMode="numeric" value={params.get('min') ?? ''} onChange={(e) => cambiar('min', e.target.value)} /></div>
        <div className="campo" style={{ width: 150 }}><label htmlFor="pr-max">Precio hasta</label><input id="pr-max" inputMode="numeric" value={params.get('max') ?? ''} onChange={(e) => cambiar('max', e.target.value)} /></div>
      </div>
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      <div className="tabla-envoltura" style={{ opacity: c.cargando && c.datos ? 0.6 : 1 }}>
        {!c.datos && !c.error && <Cargando filas={10} />}
        {c.datos && (c.datos.data.length === 0 ? <Vacio titulo="Ningún producto coincide">Quita algún filtro o busca por otra parte del nombre.</Vacio> : (
          <>
            <table className="tabla">
              <thead><tr><th>Producto</th><th>Categoría</th><th>Unidad</th><th className="num">Precio de venta</th><th className="num">Stock mínimo</th><th>Estado</th><th><span className="solo-lector">Acciones</span></th></tr></thead>
              <tbody>
                {c.datos.data.map((p) => (
                  <tr key={p.id_producto}>
                    <td><Link to={`/stock/${p.sku}`}><strong>{p.nombre}</strong></Link><span className="secundario">{p.sku} · {p.marca}</span></td>
                    <td>{categoriaRaiz(p.id_categoria).nombre}<span className="secundario">{categoriaPorId.get(p.id_categoria)!.nombre}</span></td>
                    <td>{unidad(p.unidad_medida)}</td>
                    <td className="num cifra">{dinero(p.precio_venta)}</td>
                    <td className="num cifra">{cantidad(p.stock_minimo, p.unidad_medida)}</td>
                    <td><EtiquetaEstado estado={p.estado} /></td>
                    <td>{admin && (p.estado === 'ACTIVO'
                      ? <button type="button" className="btn btn-sm btn-fantasma" onClick={() => alternar(p.id_producto, 'INACTIVO')}>Inactivar</button>
                      : <button type="button" className="btn btn-sm" onClick={() => alternar(p.id_producto, 'ACTIVO')}>Activar</button>)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Paginacion meta={c.datos.meta} cambiar={(n) => cambiar('page', String(n))} />
          </>
        ))}
      </div>
    </>
  )
}

export function Categorias() {
  const usuario = useUsuario()
  const avisar = useAvisos()
  const [alta, setAlta] = useState(false)
  const c = useConsulta(() => categoriasApi.listar(), [])
  const cuenta = (id: number) => todosProductos.filter((p) => p.id_categoria === id || categoriaRaiz(p.id_categoria).id_categoria === id).length
  return (
    <>
      <Encabezado
        titulo="Categorías"
        descripcion="No se puede inactivar una categoría que tenga productos activos."
        acciones={puedeEditar(usuario.rol, 'catalogo') && <button type="button" className="btn btn-pri" aria-expanded={alta} onClick={() => setAlta(!alta)}><Plus size={18} aria-hidden />Nueva categoría</button>}
      />
      {alta && <AltaCategoria listo={(t) => { avisar(t); setAlta(false); c.recargar() }} cancelar={() => setAlta(false)} />}
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      <div className="panel" style={{ padding: 0 }}>
        {!c.datos && !c.error && <Cargando />}
        {c.datos && (
          <ul className="arbol">
            {c.datos.map((cat) => (
              <li key={cat.id_categoria}>
                <div className="nodo"><strong>{cat.nombre}</strong><EtiquetaEstado estado={cat.estado} /><span className="cuenta">{cuenta(cat.id_categoria)} productos</span></div>
                {!!cat.subcategorias?.length && (
                  <ul className="hijos">
                    {cat.subcategorias.map((s) => <li key={s.id_categoria}><div className="nodo">{s.nombre}<span className="cuenta">{cuenta(s.id_categoria)} productos</span></div></li>)}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  )
}

export function Bodegas() {
  const usuario = useUsuario()
  const { cambiar } = useBodega()
  const navegar = useNavigate()
  const avisar = useAvisos()
  const [alta, setAlta] = useState(false)
  const c = useConsulta(() => Promise.all([bodegasApi.listar(), stockApi.listar({ per_page: 100 })]), [])
  return (
    <>
      <Encabezado
        titulo="Bodegas"
        descripcion="Cada bodega tiene su propio rack; todas se dibujan a la misma escala."
        acciones={puedeEditar(usuario.rol, 'bodegas') && <button type="button" className="btn btn-pri" aria-expanded={alta} onClick={() => setAlta(!alta)}><Plus size={18} aria-hidden />Nueva bodega</button>}
      />
      {alta && <AltaBodega listo={(t) => { avisar(t); setAlta(false); c.recargar() }} cancelar={() => setAlta(false)} />}
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      {!c.datos && !c.error && <div className="panel"><Cargando /></div>}
      {c.datos && (
        <div className="bodegas-rejilla">
          {c.datos[0].map((b) => {
            const saldos = c.datos![1].data.filter((s) => s.id_bodega === b.id_bodega)
            return (
              <article key={b.id_bodega} className="panel bodega-ficha">
                <h2>{b.nombre}<span>{b.codigo}</span></h2>
                <p style={{ color: 'var(--tinta-2)' }}>{b.direccion}</p>
                <div className="resumen-cifras" style={{ marginBottom: 0 }}>
                  <div><span>Referencias</span><strong>{saldos.length}</strong></div>
                  <div><span>Valor</span><strong>{dineroCorto(saldos.reduce((a, s) => a + s.valor, 0))}</strong></div>
                  <div><span>Stock bajo</span><strong>{saldos.filter((s) => s.bajo_minimo).length}</strong></div>
                </div>
                <div className="acciones-separadas">
                  <EtiquetaEstado estado={b.estado} />
                  {b.estado === 'ACTIVO' && <button type="button" className="btn btn-sm aparte" onClick={() => { cambiar(b.id_bodega); navegar('/stock') }}><Boxes size={16} aria-hidden />Ver su rack</button>}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </>
  )
}
