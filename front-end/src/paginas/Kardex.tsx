import { useSearchParams } from 'react-router'
import { Download } from 'lucide-react'
import { kardexApi } from '../api/cliente'
import { bodegaPorId, productoPorSku, productos } from '../api/mock/maestros'
import { esEntrada } from '../api/mock/simulacion'
import { useBodega } from '../contexto/Bodega'
import { Cargando, Encabezado, ErrorCaja, TipoMov, Vacio } from '../componentes/ui'
import { cantidad, dinero, fecha, fechaHora, nombreTipo, numeroMovimiento } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'

export function Kardex() {
  const { idBodega, activas } = useBodega()
  const [params, setParams] = useSearchParams()
  const sku = params.get('sku') ?? 'ABA-0112'
  const bodega = Number(params.get('id_bodega') ?? idBodega)
  const desde = params.get('desde') ?? '2026-10-20'
  const hasta = params.get('hasta') ?? '2026-10-29'
  const p = productoPorSku.get(sku)!
  const c = useConsulta(() => kardexApi.consultar({ sku, id_bodega: bodega, desde, hasta }), [sku, bodega, desde, hasta])
  const cambiar = (clave: string, valor: string) => {
    const n = new URLSearchParams(params)
    n.set('sku', sku); n.set('id_bodega', String(bodega)); n.set('desde', desde); n.set('hasta', hasta)
    n.set(clave, valor)
    setParams(n, { replace: true })
  }

  function exportar() {
    if (!c.datos) return
    const filas = [['Fecha', 'Documento', 'Tipo', 'Referencia', 'Entrada', 'Salida', 'Costo unitario', 'Saldo', 'Costo promedio', 'Valor']]
    for (const m of c.datos.movimientos) {
      const entra = esEntrada(m.tipo)
      filas.push([m.fecha, numeroMovimiento(m.id_movimiento), nombreTipo[m.tipo], m.documento_referencia ?? m.motivo ?? '', entra ? String(m.cantidad) : '', entra ? '' : String(m.cantidad), String(m.costo_unitario), String(m.saldo_resultante), String(m.costo_promedio), String(m.valor_resultante)])
    }
    const csv = filas.map((f) => f.map((x) => `"${x.replace(/"/g, '""')}"`).join(';')).join('\r\n')
    const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `kardex-${sku}-${bodegaPorId.get(bodega)!.codigo}-${desde}-${hasta}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <Encabezado
        titulo="Kardex"
        codigo={sku}
        descripcion={`${p.nombre} en ${bodegaPorId.get(bodega)!.nombre}, valorizado a costo promedio ponderado.`}
        acciones={<button type="button" className="btn" onClick={exportar} disabled={!c.datos}><Download size={18} aria-hidden />Exportar CSV</button>}
      />
      <div className="filtros">
        <div className="campo ancho">
          <label htmlFor="k-sku">Producto</label>
          <select id="k-sku" value={sku} onChange={(e) => cambiar('sku', e.target.value)}>
            {productos.map((x) => <option key={x.sku} value={x.sku}>{x.sku} · {x.nombre}</option>)}
          </select>
        </div>
        <div className="campo">
          <label htmlFor="k-bodega">Bodega</label>
          <select id="k-bodega" value={bodega} onChange={(e) => cambiar('id_bodega', e.target.value)}>
            {activas.map((b) => <option key={b.id_bodega} value={b.id_bodega}>{b.codigo} · {b.nombre}</option>)}
          </select>
        </div>
        <div className="campo"><label htmlFor="k-desde">Desde</label><input id="k-desde" type="date" value={desde} onChange={(e) => cambiar('desde', e.target.value)} /></div>
        <div className="campo"><label htmlFor="k-hasta">Hasta</label><input id="k-hasta" type="date" value={hasta} onChange={(e) => cambiar('hasta', e.target.value)} /></div>
      </div>

      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      <div className="tabla-envoltura">
        {!c.datos && !c.error && <Cargando filas={10} />}
        {c.datos && (
          <table className="tabla">
            <thead>
              <tr className="grupo-col">
                <th colSpan={3} /><th colSpan={2} className="sep-izq">Entradas</th><th colSpan={2} className="sep-izq">Salidas</th><th colSpan={3} className="sep-izq">Saldo</th>
              </tr>
              <tr>
                <th>Fecha</th><th>Documento</th><th>Referencia</th>
                <th className="num sep-izq">Cantidad</th><th className="num">Costo u.</th>
                <th className="num sep-izq">Cantidad</th><th className="num">Costo u.</th>
                <th className="num sep-izq">Cantidad</th><th className="num">Costo prom.</th><th className="num">Valor</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={3}><strong>Saldo inicial al {fecha(desde + 'T12:00:00Z')}</strong></td>
                <td className="sep-izq" colSpan={2} /><td className="sep-izq" colSpan={2} />
                <td className="num cifra sep-izq"><strong>{cantidad(c.datos.saldo_inicial.cantidad, p.unidad_medida, false)}</strong></td><td />
                <td className="num cifra"><strong>{dinero(c.datos.saldo_inicial.valor)}</strong></td>
              </tr>
              {c.datos.movimientos.length === 0 && (
                <tr><td colSpan={10}><Vacio titulo="Sin movimientos en este rango" /></td></tr>
              )}
              {c.datos.movimientos.map((m) => {
                const entra = esEntrada(m.tipo)
                return (
                  <tr key={m.id_movimiento}>
                    <td className="cifra">{fechaHora(m.fecha)}</td>
                    <td><span className="doc">{numeroMovimiento(m.id_movimiento)}</span><span className="secundario"><TipoMov tipo={m.tipo} /></span></td>
                    <td>{m.documento_referencia ?? m.motivo ?? '—'}</td>
                    <td className="num cifra sep-izq">{entra ? <span className="mas">{cantidad(m.cantidad, p.unidad_medida, false)}</span> : ''}</td>
                    <td className="num cifra">{entra ? dinero(m.costo_unitario) : ''}</td>
                    <td className="num cifra sep-izq">{!entra ? <span className={m.tipo === 'AJUSTE_NEGATIVO' ? 'merma' : 'menos'}>{cantidad(m.cantidad, p.unidad_medida, false)}</span> : ''}</td>
                    <td className="num cifra">{!entra ? dinero(m.costo_unitario) : ''}</td>
                    <td className="num cifra sep-izq"><strong>{cantidad(m.saldo_resultante, p.unidad_medida, false)}</strong></td>
                    <td className="num cifra">{dinero(m.costo_promedio)}</td>
                    <td className="num cifra">{dinero(m.valor_resultante)}</td>
                  </tr>
                )
              })}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={3}><strong>Saldo final al {fecha(hasta + 'T12:00:00Z')}</strong></td>
                <td className="sep-izq" colSpan={2} /><td className="sep-izq" colSpan={2} />
                <td className="num cifra sep-izq"><strong>{cantidad(c.datos.saldo_final.cantidad, p.unidad_medida)}</strong></td><td />
                <td className="num cifra"><strong>{dinero(c.datos.saldo_final.valor)}</strong></td>
              </tr>
            </tfoot>
          </table>
        )}
      </div>
    </>
  )
}
