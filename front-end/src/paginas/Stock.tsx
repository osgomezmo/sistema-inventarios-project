import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { PackageX, Plus, ScrollText, X } from 'lucide-react'
import { proveedoresApi, stockApi } from '../api/cliente'
import { bodegaPorId, categoriaRaiz, productoPorSku } from '../api/mock/maestros'
import { useUsuario } from '../auth/Sesion'
import { puedeEditar, puedeVer } from '../auth/permisos'
import { useBodega } from '../contexto/Bodega'
import { Cargando, Encabezado, ErrorCaja, EtiquetaSaldo, Vacio } from '../componentes/ui'
import { cantidad, dinero } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'
import { RackBodega } from '../tres/RackDiferido'

export function Stock() {
  const usuario = useUsuario()
  const { idBodega, bodega } = useBodega()
  const navegar = useNavigate()
  const [params, setParams] = useSearchParams()
  const soloBajo = params.get('bajo') === '1'
  const [q, setQ] = useState('')
  const [seleccionado, setSeleccionado] = useState<string | null>(params.get('sku'))

  const c = useConsulta(() => stockApi.listar({ id_bodega: idBodega, per_page: 100 }), [idBodega])

  const filas = useMemo(() => {
    const t = q.trim().toLowerCase()
    return (c.datos?.data ?? []).filter((s) => {
      if (seleccionado) return s.sku === seleccionado
      const p = productoPorSku.get(s.sku)!
      return (!soloBajo || s.bajo_minimo) && (!t || s.sku.toLowerCase().includes(t) || p.nombre.toLowerCase().includes(t))
    })
  }, [c.datos, q, soloBajo, seleccionado])

  const total = filas.reduce((a, s) => a + s.valor, 0)
  const verKardex = (sku: string) => navegar(`/kardex?sku=${sku}&id_bodega=${idBodega}`)

  return (
    <>
      <Encabezado
        titulo={`Stock de ${bodega.nombre}`}
        codigo={bodega.codigo}
        descripcion="Elige una posición en el rack o una fila de la tabla: las dos vistas muestran el mismo producto."
        acciones={puedeEditar(usuario.rol, 'movimientos') && <Link className="btn btn-pri" to="/movimientos/nuevo"><Plus size={18} aria-hidden />Registrar movimiento</Link>}
      />

      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      {!c.datos && !c.error && <div className="panel"><Cargando filas={8} /></div>}

      {c.datos && (
        <div className="pila">
          <RackBodega
            saldos={c.datos.data}
            codigoBodega={bodega.codigo}
            nombreBodega={bodega.nombre}
            seleccionado={seleccionado}
            onSeleccionar={setSeleccionado}
            onVerKardex={puedeVer(usuario.rol, 'movimientos') ? verKardex : undefined}
            alto={440}
          />

          <section>
            <div className="filtros">
              <div className="campo ancho">
                <label htmlFor="f-q">Buscar en esta bodega</label>
                <input id="f-q" type="search" placeholder="SKU o nombre" value={q} onChange={(e) => setQ(e.target.value)} />
              </div>
              <div className="chips" role="group" aria-label="Filtro de estado" style={{ marginBottom: 0 }}>
                <button type="button" className="chip" aria-pressed={!soloBajo && !seleccionado} onClick={() => { setSeleccionado(null); setParams({}) }}>Todos</button>
                <button type="button" className="chip" aria-pressed={soloBajo && !seleccionado} onClick={() => { setSeleccionado(null); setParams({ bajo: '1' }) }}>Solo stock bajo</button>
                {seleccionado && (
                  <button type="button" className="chip chip-seleccion" aria-pressed="true" onClick={() => setSeleccionado(null)}>
                    Posición {seleccionado} · Quitar selección <X size={16} aria-hidden />
                  </button>
                )}
              </div>
            </div>

            <div className="tabla-envoltura">
              {filas.length === 0 ? (
                <Vacio titulo={soloBajo ? 'Ningún producto bajo el mínimo' : 'Sin resultados'} icono={<PackageX size={40} aria-hidden />}>
                  {soloBajo ? `Todas las posiciones de ${bodega.codigo} están por encima de su mínimo.` : 'Prueba con otro SKU o nombre.'}
                </Vacio>
              ) : (
                <table className="tabla tabla-apilable">
                  <thead>
                    <tr>
                      <th>Producto</th><th>Categoría</th><th className="num">Saldo</th><th className="num">Mínimo</th>
                      <th className="num">Costo promedio</th><th className="num">Valor</th><th>Estado</th><th><span className="solo-lector">Acciones</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {filas.map((s) => {
                      const p = productoPorSku.get(s.sku)!
                      const activo = seleccionado === s.sku
                      return (
                        <tr key={s.sku} className="fila-boton" aria-selected={activo} tabIndex={0}
                          onClick={() => setSeleccionado(activo ? null : s.sku)}
                          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSeleccionado(activo ? null : s.sku) } }}>
                          <td><strong>{p.nombre}</strong><span className="secundario">{s.sku} · {p.marca}</span></td>
                          <td data-etiqueta="Categoría">{categoriaRaiz(p.id_categoria).nombre}</td>
                          <td className="num cifra" data-etiqueta="Saldo"><strong>{cantidad(s.cantidad, p.unidad_medida)}</strong></td>
                          <td className="num cifra" data-etiqueta="Mínimo">{cantidad(s.stock_minimo, p.unidad_medida)}</td>
                          <td className="num cifra" data-etiqueta="Costo prom.">{dinero(s.costo_promedio)}</td>
                          <td className="num cifra" data-etiqueta="Valor">{dinero(s.valor)}</td>
                          <td><EtiquetaSaldo saldo={s} /></td>
                          <td><Link to={`/stock/${s.sku}`} onClick={(e) => e.stopPropagation()}>Detalle</Link></td>
                        </tr>
                      )
                    })}
                  </tbody>
                  <tfoot>
                    <tr><td colSpan={5}><strong>Total de {filas.length} referencias</strong></td><td className="num cifra"><strong>{dinero(total)}</strong></td><td colSpan={2} /></tr>
                  </tfoot>
                </table>
              )}
            </div>
          </section>
        </div>
      )}
    </>
  )
}

export function StockDetalle() {
  const { sku = '' } = useParams()
  const usuario = useUsuario()
  const p = productoPorSku.get(sku)
  const c = useConsulta(() => Promise.all([stockApi.porSku(sku), proveedoresApi.listar({ sku })]), [sku])

  if (!p) return <div className="panel"><Vacio titulo={`No existe el producto ${sku}`} accion={<Link className="btn" to="/stock">Volver al stock</Link>} /></div>

  return (
    <>
      <Encabezado
        migas={<><Link to="/stock">Stock</Link><span aria-hidden>/</span><span>{sku}</span></>}
        titulo={p.nombre}
        codigo={p.sku}
        descripcion={`${p.marca} · ${categoriaRaiz(p.id_categoria).nombre} · stock mínimo ${cantidad(p.stock_minimo, p.unidad_medida)} por bodega`}
        acciones={puedeVer(usuario.rol, 'movimientos') && <Link className="btn" to={`/kardex?sku=${sku}`}><ScrollText size={18} aria-hidden />Ver kardex</Link>}
      />
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      {!c.datos && !c.error && <div className="panel"><Cargando /></div>}
      {c.datos && (() => {
        const [stock, provs] = c.datos
        return (
          <div className="dos-columnas">
            <section className="tabla-envoltura" aria-labelledby="t-porbodega">
              <div className="panel-titulo" style={{ padding: '16px 16px 0' }}><h2 id="t-porbodega">Saldo por bodega</h2></div>
              <table className="tabla">
                <thead><tr><th>Bodega</th><th className="num">Saldo</th><th className="num">Costo promedio</th><th className="num">Valor</th><th>Estado</th></tr></thead>
                <tbody>
                  {stock.por_bodega.map((b) => (
                    <tr key={b.id_bodega}>
                      <td><strong>{bodegaPorId.get(b.id_bodega)!.nombre}</strong><span className="secundario">{bodegaPorId.get(b.id_bodega)!.codigo}</span></td>
                      <td className="num cifra">{cantidad(b.cantidad, p.unidad_medida)}</td>
                      <td className="num cifra">{dinero(b.costo_promedio)}</td>
                      <td className="num cifra">{dinero(b.valor)}</td>
                      <td><EtiquetaSaldo saldo={{ cantidad: b.cantidad, stock_minimo: p.stock_minimo }} /></td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr><td><strong>Consolidado</strong></td><td className="num cifra"><strong>{cantidad(stock.total.cantidad, p.unidad_medida)}</strong></td><td /><td className="num cifra"><strong>{dinero(stock.total.valor)}</strong></td><td /></tr>
                </tfoot>
              </table>
            </section>
            <aside className="panel">
              <h2>Proveedores que lo suministran</h2>
              {provs.data.length === 0 ? <p>Ningún proveedor activo tiene este producto.</p> : (
                <ul className="lista-rotacion" style={{ gap: 12 }}>
                  {provs.data.map((pr) => <li key={pr.id_proveedor}><Link to={`/proveedores/${pr.id_proveedor}`}>{pr.razon_social}</Link><span>{pr.nit}</span></li>)}
                </ul>
              )}
            </aside>
          </div>
        )
      })()}
    </>
  )
}
