import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { Download, Printer } from 'lucide-react'
import type { AgruparValorizacion } from '../api/types'
import { reportesApi } from '../api/cliente'
import { bodegaPorId, productoPorSku } from '../api/mock/maestros'
import { useBodega } from '../contexto/Bodega'
import { BarrasH } from '../componentes/Graficas'
import { Cargando, Encabezado, ErrorCaja, EtiquetaSaldo, Vacio } from '../componentes/ui'
import { cantidad, dinero, dineroCorto, fechaHora } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'

function descargarCsv(nombre: string, filas: string[][]) {
  const csv = filas.map((f) => f.map((x) => `"${String(x).replace(/"/g, '""')}"`).join(';')).join('\r\n')
  const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = nombre
  a.click()
  URL.revokeObjectURL(url)
}

export function Reportes() {
  const [params, setParams] = useSearchParams()
  const pestana = params.get('reporte') ?? 'valorizacion'
  return (
    <>
      <Encabezado
        titulo="Reportes"
        descripcion="Los genera ms-reportes con los eventos de inventario y compras; se exportan a CSV y, desde el servidor, a PDF."
        acciones={<button type="button" className="btn" onClick={() => window.print()}><Printer size={18} aria-hidden />Imprimir o guardar PDF</button>}
      />
      <div className="pestanas" role="tablist">
        {[['valorizacion', 'Valorización'], ['rotacion', 'Rotación'], ['stock-bajo', 'Stock bajo']].map(([id, texto]) => (
          <button key={id} type="button" role="tab" aria-selected={pestana === id} onClick={() => setParams({ reporte: id })}>{texto}</button>
        ))}
      </div>
      {pestana === 'valorizacion' && <Valorizacion />}
      {pestana === 'rotacion' && <Rotacion />}
      {pestana === 'stock-bajo' && <StockBajo />}
    </>
  )
}

function FiltroBodega({ valor, cambiar }: { valor: number; cambiar: (n: number) => void }) {
  const { activas } = useBodega()
  return (
    <div className="campo">
      <label htmlFor="r-bodega">Bodega</label>
      <select id="r-bodega" value={valor} onChange={(e) => cambiar(Number(e.target.value))}>
        <option value={0}>Todas</option>
        {activas.map((b) => <option key={b.id_bodega} value={b.id_bodega}>{b.codigo} · {b.nombre}</option>)}
      </select>
    </div>
  )
}

function Valorizacion() {
  const [agrupar, setAgrupar] = useState<AgruparValorizacion>('categoria')
  const [bodega, setBodega] = useState(0)
  const c = useConsulta(() => reportesApi.valorizacion(agrupar, bodega || undefined), [agrupar, bodega])
  const total = c.datos?.reduce((a, f) => a + f.valor, 0) ?? 0
  return (
    <section role="tabpanel" className="pila">
      <div className="filtros" style={{ marginBottom: 0 }}>
        <div className="campo">
          <label htmlFor="r-agrupar">Agrupar por</label>
          <select id="r-agrupar" value={agrupar} onChange={(e) => setAgrupar(e.target.value as AgruparValorizacion)}>
            <option value="categoria">Categoría</option><option value="bodega">Bodega</option><option value="producto">Producto</option>
          </select>
        </div>
        <FiltroBodega valor={bodega} cambiar={setBodega} />
        <button type="button" className="btn" disabled={!c.datos} onClick={() => descargarCsv(`valorizacion-${agrupar}.csv`, [['Clave', 'Nombre', 'Cantidad', 'Valor'], ...(c.datos ?? []).map((f) => [f.clave, f.nombre, String(f.cantidad), String(Math.round(f.valor))])])}>
          <Download size={18} aria-hidden />Exportar CSV
        </button>
      </div>
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      {!c.datos && !c.error && <div className="panel"><Cargando /></div>}
      {c.datos && (
        <div className="dos-columnas">
          <div className="panel">
            <h2>Valor del inventario por {agrupar === 'categoria' ? 'categoría' : agrupar}</h2>
            <p style={{ color: 'var(--tinta-2)', marginBottom: 16 }}>Total {dinero(total)} a costo promedio ponderado.</p>
            <BarrasH etiqueta="Valor del inventario" filas={c.datos.slice(0, 12).map((f) => ({ clave: f.clave, nombre: f.nombre, valor: f.valor }))} formato={dineroCorto} />
          </div>
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead><tr><th>{agrupar === 'producto' ? 'Producto' : agrupar === 'bodega' ? 'Bodega' : 'Categoría'}</th><th className="num">Valor</th><th className="num">Participación</th></tr></thead>
              <tbody>{c.datos.map((f) => <tr key={f.clave}><td>{f.nombre}</td><td className="num cifra">{dinero(f.valor)}</td><td className="num cifra">{total ? ((f.valor / total) * 100).toLocaleString('es-CO', { maximumFractionDigits: 1 }) : 0} %</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}

function Rotacion() {
  const [desde, setDesde] = useState('2026-10-01')
  const [hasta, setHasta] = useState('2026-10-29')
  const [bodega, setBodega] = useState(0)
  const c = useConsulta(() => reportesApi.rotacion({ desde, hasta, id_bodega: bodega || undefined, top: 8 }), [desde, hasta, bodega])
  const veces = (v: number) => `${v.toLocaleString('es-CO', { maximumFractionDigits: 2 })} veces`
  return (
    <section role="tabpanel" className="pila">
      <div className="filtros" style={{ marginBottom: 0 }}>
        <div className="campo"><label htmlFor="r-desde">Desde</label><input id="r-desde" type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></div>
        <div className="campo"><label htmlFor="r-hasta">Hasta</label><input id="r-hasta" type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></div>
        <FiltroBodega valor={bodega} cambiar={setBodega} />
        <button type="button" className="btn" disabled={!c.datos} onClick={() => descargarCsv('rotacion.csv', [['SKU', 'Producto', 'Unidades de salida', 'Rotación'], ...[...(c.datos?.mayor_rotacion ?? []), ...(c.datos?.menor_rotacion ?? [])].map((r) => [r.sku, r.nombre, String(r.unidades_salida), String(r.rotacion)])])}>
          <Download size={18} aria-hidden />Exportar CSV
        </button>
      </div>
      <p style={{ color: 'var(--tinta-2)' }}>Rotación = unidades que salieron en el periodo divididas por el saldo promedio al cierre de cada día.</p>
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      {!c.datos && !c.error && <div className="panel"><Cargando /></div>}
      {c.datos && (
        <div className="tablero-inferior">
          <div className="panel"><h2>Mayor rotación</h2><BarrasH etiqueta="Productos de mayor rotación" filas={c.datos.mayor_rotacion.map((r) => ({ clave: r.sku, nombre: r.nombre, valor: r.rotacion }))} formato={veces} /></div>
          <div className="panel"><h2>Menor rotación</h2><BarrasH etiqueta="Productos de menor rotación" filas={c.datos.menor_rotacion.map((r) => ({ clave: r.sku, nombre: r.nombre, valor: r.rotacion }))} formato={veces} /></div>
        </div>
      )}
    </section>
  )
}

function StockBajo() {
  const [bodega, setBodega] = useState(0)
  const c = useConsulta(() => reportesApi.stockBajo(bodega || undefined), [bodega])
  return (
    <section role="tabpanel" className="pila">
      <div className="filtros" style={{ marginBottom: 0 }}><FiltroBodega valor={bodega} cambiar={setBodega} /></div>
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      <div className="tabla-envoltura">
        {!c.datos && !c.error && <Cargando />}
        {c.datos && (c.datos.length === 0 ? <Vacio titulo="Ninguna alerta activa" /> : (
          <table className="tabla">
            <thead><tr><th>Producto</th><th>Bodega</th><th className="num">Saldo</th><th className="num">Mínimo</th><th>Estado</th><th>Desde</th></tr></thead>
            <tbody>
              {c.datos.map((a) => {
                const p = productoPorSku.get(a.sku)!
                return <tr key={`${a.sku}-${a.id_bodega}`}><td>{p.nombre}<span className="secundario">{a.sku}</span></td><td>{bodegaPorId.get(a.id_bodega)!.codigo}</td><td className="num cifra">{cantidad(a.saldo, p.unidad_medida)}</td><td className="num cifra">{cantidad(a.stock_minimo, p.unidad_medida)}</td><td><EtiquetaSaldo saldo={{ cantidad: a.saldo, stock_minimo: a.stock_minimo }} /></td><td className="cifra">{fechaHora(a.fecha)}</td></tr>
              })}
            </tbody>
          </table>
        ))}
      </div>
    </section>
  )
}
