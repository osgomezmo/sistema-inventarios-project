import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { ArrowRightLeft, ClipboardList, Plus } from 'lucide-react'
import { AHORA, movimientosApi, reportesApi, stockApi } from '../api/cliente'
import { productoPorSku } from '../api/mock/maestros'
import { useUsuario } from '../auth/Sesion'
import { puedeEditar, puedeVer } from '../auth/permisos'
import { useBodega } from '../contexto/Bodega'
import { LineaValor } from '../componentes/Graficas'
import { CantidadMov, Cargando, Encabezado, ErrorCaja, EtiquetaSaldo, TipoMov, Vacio } from '../componentes/ui'
import { cantidad, diaLocal, dineroCorto, fechaHora, hora, numero, numeroMovimiento } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'
import { RackBodega } from '../tres/RackDiferido'

export function Dashboard() {
  const usuario = useUsuario()
  const { idBodega, bodega } = useBodega()
  const navegar = useNavigate()
  const [seleccionado, setSeleccionado] = useState<string | null>(null)

  const c = useConsulta(() => Promise.all([
    reportesApi.dashboard(idBodega),
    stockApi.listar({ id_bodega: idBodega, per_page: 100 }),
    reportesApi.stockBajo(idBodega),
    movimientosApi.listar({ id_bodega: idBodega, per_page: 8 }),
    reportesApi.serieValor(idBodega),
    movimientosApi.listar({ id_bodega: idBodega, desde: diaLocal(AHORA) + 'T05:00:00Z', per_page: 1 }),
  ]), [idBodega])

  const verKardex = (sku: string) => navegar(`/kardex?sku=${sku}&id_bodega=${idBodega}`)
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
        descripcion={<>Saldos al {fechaHora(AHORA)}{c.datos && <> · {numero(c.datos[1].meta.total)} referencias en el rack</>}</>}
        acciones={acciones}
      />

      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      {!c.datos && !c.error && <div className="panel"><Cargando filas={10} /></div>}

      {c.datos && (() => {
        const [d, stock, bajos, recientes, serie, hoy] = c.datos
        const inicio = serie[0]?.valor ?? 0
        const haceSiete = serie.at(-8)?.valor ?? inicio
        const pct = (base: number) => (base ? Math.round(((d.valor_total_inventario - base) / base) * 100) : 0)
        const conSigno = (n: number) => `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n)} %`
        return (
          <div className="tablero">
            <section aria-label="Rack de la bodega" className="tablero-rack">
              <RackBodega
                saldos={stock.data}
                codigoBodega={bodega.codigo}
                nombreBodega={bodega.nombre}
                seleccionado={seleccionado}
                onSeleccionar={setSeleccionado}
                onVerKardex={puedeVer(usuario.rol, 'movimientos') ? verKardex : undefined}
                alto="100%"
              />
            </section>

            <aside className="panel" aria-label="Indicadores">
              <h2>Indicadores de {bodega.codigo}</h2>
              <div className="indicadores">
                <div className="indicador">
                  <span className="indicador-nombre">Valor del inventario</span>
                  <span className="indicador-valor">{dineroCorto(d.valor_total_inventario)}</span>
                  <span className="indicador-nota">{conSigno(pct(haceSiete))} en 7 días · {conSigno(pct(inicio))} en octubre, con {d.ordenes_pendientes} órdenes por recibir</span>
                  <div className="indicador-grafica"><LineaValor serie={serie} etiqueta={`Valor diario del inventario de ${bodega.nombre} en octubre`} /></div>
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
                <div className="indicador">
                  <span className="indicador-nombre">Movimientos hoy</span>
                  <span className="indicador-valor">{numero(hoy.meta.total)}</span>
                </div>
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
                      {bajos.map((a) => {
                        const p = productoPorSku.get(a.sku)!
                        return (
                          <tr key={a.sku} className="fila-boton" aria-selected={seleccionado === a.sku} tabIndex={0}
                            onClick={() => setSeleccionado(seleccionado === a.sku ? null : a.sku)}
                            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSeleccionado(a.sku) } }}>
                            <td><strong>{p.nombre}</strong><span className="secundario">{a.sku}</span></td>
                            <td className="num cifra" data-etiqueta="Saldo">{cantidad(a.saldo, p.unidad_medida)}</td>
                            <td className="num cifra" data-etiqueta="Mínimo">{cantidad(a.stock_minimo, p.unidad_medida)}</td>
                            <td><EtiquetaSaldo saldo={{ cantidad: a.saldo, stock_minimo: a.stock_minimo }} /></td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )}
              </section>

              {puedeVer(usuario.rol, 'movimientos') && (
                <section className="tabla-envoltura" aria-labelledby="t-mov">
                  <div className="panel-titulo" style={{ padding: '16px 16px 0' }}>
                    <h2 id="t-mov">Movimientos recientes</h2>
                    <Link to="/movimientos">Ver movimientos</Link>
                  </div>
                  <table className="tabla tabla-apilable">
                    <thead><tr><th>Documento</th><th>Producto</th><th className="num">Cantidad</th><th className="num">Hora</th></tr></thead>
                    <tbody>
                      {recientes.data.map((m) => (
                        <tr key={m.id_movimiento}>
                          <td><span className="doc">{numeroMovimiento(m.id_movimiento)}</span><span className="secundario"><TipoMov tipo={m.tipo} /></span></td>
                          <td>{productoPorSku.get(m.sku)!.nombre}</td>
                          <td className="num"><CantidadMov m={m} /></td>
                          <td className="num cifra">{diaLocal(m.fecha) === diaLocal(AHORA) ? hora(m.fecha) : fechaHora(m.fecha)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
              )}
            </div>
          </div>
        )
      })()}
    </>
  )
}
