import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { ArrowRightLeft, ClipboardList, Plus } from 'lucide-react'
import { movimientosApi, reportesApi, stockApi } from '../api/cliente'
import { producto } from '../api/maestros'
import { useUsuario } from '../auth/Sesion'
import { puedeEditar, puedeVer } from '../auth/permisos'
import { useBodega } from '../contexto/Bodega'
import { useMaestros } from '../contexto/Maestros'
import { CantidadMov, Cargando, Encabezado, ErrorCaja, EtiquetaSaldo, TipoMov, Vacio } from '../componentes/ui'
import { cantidad, diaLocal, dineroCorto, fechaHora, hora, hoy, numero, numeroMovimiento } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'
import { RackBodega } from '../tres/RackDiferido'

export function Dashboard() {
  const usuario = useUsuario()
  useMaestros()
  const { idBodega, bodega } = useBodega()
  const navegar = useNavigate()
  const [seleccionado, setSeleccionado] = useState<string | null>(null)
  const verMov = puedeVer(usuario.rol, 'movimientos')

  // El rack, el stock bajo y los movimientos salen de ms-inventario; los indicadores, de ms-reportes.
  const c = useConsulta(() => Promise.all([
    stockApi.todos({ id_bodega: idBodega }),
    verMov ? movimientosApi.listar({ id_bodega: idBodega, per_page: 8 }) : Promise.resolve(null),
    verMov ? movimientosApi.listar({ id_bodega: idBodega, desde: hoy(), per_page: 1 }) : Promise.resolve(null),
    Promise.resolve(new Date().toISOString()),
  ]), [idBodega, verMov])
  const rep = useConsulta(() => reportesApi.dashboard(idBodega), [idBodega])

  const verKardex = (sku: string) => navegar(`/kardex?sku=${encodeURIComponent(sku)}&id_bodega=${idBodega}`)
  const editaMov = puedeEditar(usuario.rol, 'movimientos')

  const acciones = (
    <>
      {editaMov && <Link className="btn" to="/traslados/nuevo"><ArrowRightLeft size={18} aria-hidden />Nuevo traslado</Link>}
      {editaMov && <Link className="btn btn-pri" to="/movimientos/nuevo"><Plus size={18} aria-hidden />Registrar movimiento</Link>}
      {!editaMov && puedeEditar(usuario.rol, 'ordenes') && <Link className="btn btn-pri" to="/ordenes-compra/nueva"><Plus size={18} aria-hidden />Nueva orden de compra</Link>}
      {usuario.rol === 'GERENTE' && <Link className="btn btn-pri" to="/ordenes-compra?estado=BORRADOR"><ClipboardList size={18} aria-hidden />Órdenes por aprobar</Link>}
    </>
  )

  return (
    <>
      <Encabezado
        titulo={bodega.nombre}
        codigo={bodega.codigo}
        descripcion={c.datos ? <>Saldos al {fechaHora(c.datos[3])} · {numero(c.datos[0].length)} referencias en el rack</> : 'Consultando los saldos de la bodega…'}
        acciones={acciones}
      />

      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      {!c.datos && !c.error && <div className="panel"><Cargando filas={10} /></div>}

      {c.datos && (() => {
        const [saldos, recientes, deHoy] = c.datos
        const bajos = saldos.filter((s) => s.bajo_minimo).sort((a, b) => a.cantidad / (a.stock_minimo || 1) - b.cantidad / (b.stock_minimo || 1))
        const d = rep.datos
        return (
          <div className="tablero">
            <section aria-label="Rack de la bodega" className="tablero-rack">
              <RackBodega
                saldos={saldos}
                codigoBodega={bodega.codigo}
                nombreBodega={bodega.nombre}
                seleccionado={seleccionado}
                onSeleccionar={setSeleccionado}
                onVerKardex={verMov ? verKardex : undefined}
                alto="100%"
              />
            </section>

            <aside className="panel" aria-label="Indicadores">
              <h2>Indicadores de {bodega.codigo}</h2>
              {rep.error && <ErrorCaja error={rep.error} reintentar={rep.recargar} />}
              {!d && !rep.error && <Cargando filas={4} texto="Cargando indicadores" />}
              <div className="indicadores">
                {d && (
                  <>
                    <div className="indicador">
                      <span className="indicador-nombre">Valor del inventario</span>
                      <span className="indicador-valor">{dineroCorto(d.valor_total_inventario)}</span>
                      <span className="indicador-nota">A costo promedio ponderado</span>
                    </div>
                    <Link className="indicador" to="/stock?bajo=1">
                      <span className="indicador-nombre">Productos en stock bajo</span>
                      <span className={`indicador-valor${d.productos_stock_bajo ? ' con-franja' : ''}`}>{d.productos_stock_bajo}</span>
                    </Link>
                    <Link className="indicador" to="/ordenes-compra">
                      <span className="indicador-nombre">Órdenes pendientes</span>
                      <span className="indicador-valor">{d.ordenes_pendientes}</span>
                      <span className="indicador-nota">En borrador, aprobadas o recibidas parcialmente</span>
                    </Link>
                  </>
                )}
                {deHoy && (
                  <div className="indicador">
                    <span className="indicador-nombre">Movimientos hoy</span>
                    <span className="indicador-valor">{numero(deHoy.meta.total)}</span>
                  </div>
                )}
                {d && (
                  <>
                    <div className="indicador">
                      <span className="indicador-nombre">Mayor rotación</span>
                      <ul className="lista-rotacion">
                        {d.mayor_rotacion.slice(0, 3).map((r) => <li key={r.sku}><span>{r.nombre}</span><span>{r.rotacion.toLocaleString('es-CO')} veces</span></li>)}
                      </ul>
                    </div>
                    <div className="indicador">
                      <span className="indicador-nombre">Menor rotación</span>
                      <ul className="lista-rotacion">
                        {d.menor_rotacion.slice(0, 3).map((r) => <li key={r.sku}><span>{r.nombre}</span><span>{r.rotacion.toLocaleString('es-CO')} veces</span></li>)}
                      </ul>
                    </div>
                  </>
                )}
              </div>
            </aside>

            <div className="tablero-inferior ancho-completo">
              <section className="tabla-envoltura" aria-labelledby="t-bajo">
                <div className="panel-titulo" style={{ padding: '16px 16px 0' }}>
                  <h2 id="t-bajo">Stock bajo en {bodega.nombre}</h2>
                  <Link to="/stock?bajo=1">Ver todo el stock</Link>
                </div>
                {bajos.length === 0 ? (
                  <Vacio titulo="Ningún producto bajo el mínimo">Todas las posiciones de {bodega.codigo} están por encima de su stock mínimo.</Vacio>
                ) : (
                  <table className="tabla tabla-apilable">
                    <thead><tr><th>Producto</th><th className="num">Saldo</th><th className="num">Mínimo</th><th>Estado</th></tr></thead>
                    <tbody>
                      {bajos.map((s) => {
                        const p = producto(s.sku)
                        return (
                          <tr key={s.sku} className="fila-boton" aria-selected={seleccionado === s.sku} tabIndex={0}
                            onClick={() => setSeleccionado(seleccionado === s.sku ? null : s.sku)}
                            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSeleccionado(s.sku) } }}>
                            <td><strong>{p.nombre}</strong><span className="secundario">{s.sku}</span></td>
                            <td className="num cifra" data-etiqueta="Saldo">{cantidad(s.cantidad, p.unidad_medida)}</td>
                            <td className="num cifra" data-etiqueta="Mínimo">{cantidad(s.stock_minimo, p.unidad_medida)}</td>
                            <td><EtiquetaSaldo saldo={s} /></td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )}
              </section>

              {recientes && (
                <section className="tabla-envoltura" aria-labelledby="t-mov">
                  <div className="panel-titulo" style={{ padding: '16px 16px 0' }}>
                    <h2 id="t-mov">Movimientos recientes</h2>
                    <Link to="/movimientos">Ver movimientos</Link>
                  </div>
                  {recientes.data.length === 0 ? <Vacio titulo="Aún no hay movimientos en esta bodega" /> : (
                    <table className="tabla tabla-apilable">
                      <thead><tr><th>Documento</th><th>Producto</th><th className="num">Cantidad</th><th className="num">Hora</th></tr></thead>
                      <tbody>
                        {recientes.data.map((m) => (
                          <tr key={m.id_movimiento}>
                            <td><span className="doc">{numeroMovimiento(m.id_movimiento)}</span><span className="secundario"><TipoMov tipo={m.tipo} /></span></td>
                            <td>{producto(m.sku).nombre}</td>
                            <td className="num"><CantidadMov m={m} /></td>
                            <td className="num cifra">{diaLocal(m.fecha) === hoy() ? hora(m.fecha) : fechaHora(m.fecha)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </section>
              )}
            </div>
          </div>
        )
      })()}
    </>
  )
}
