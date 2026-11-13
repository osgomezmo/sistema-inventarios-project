// Gráficas de una sola serie: sin leyenda (el título dice qué se grafica), tinta para la
// marca, rejilla de 1 px, valor rotulado solo en el extremo y detalle al pasar el puntero.
import { useId, useMemo, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { dinero, dineroCorto } from '../lib/formato'

const TINTA = '#17181b'
const REJILLA = '#d6d6d1'

const fechaCorta = (dia: string) =>
  new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(new Date(dia + 'T12:00:00Z'))

/** Valor diario con cruz de lectura; las flechas del teclado recorren los días. */
export function LineaValor({ serie, alto = 120, etiqueta }: { serie: Array<{ dia: string; valor: number }>; alto?: number; etiqueta: string }) {
  const [activo, setActivo] = useState<number | null>(null)
  const id = useId()
  const ancho = 320
  const m = { izq: 54, der: 58, arr: 10, aba: 24 }
  const { puntos, ticks, x, y } = useMemo(() => {
    const valores = serie.map((p) => p.valor)
    const paso = 10_000_000
    const min = Math.floor(Math.min(...valores) / paso) * paso
    const max = Math.ceil(Math.max(...valores) / paso) * paso
    const x = (i: number) => m.izq + (i / Math.max(serie.length - 1, 1)) * (ancho - m.izq - m.der)
    const y = (v: number) => m.arr + (1 - (v - min) / Math.max(max - min, 1)) * (alto - m.arr - m.aba)
    const ticks = [min, (min + max) / 2, max]
    return { puntos: serie.map((p, i) => [x(i), y(p.valor)] as const), ticks, x, y }
  }, [serie, alto, m.izq, m.der, m.arr, m.aba])

  if (!serie.length) return null
  const ultimo = serie.length - 1
  const linea = puntos.map(([px, py], i) => `${i ? 'L' : 'M'}${px.toFixed(1)},${py.toFixed(1)}`).join(' ')
  const area = `${linea} L${puntos[ultimo][0]},${alto - m.aba} L${puntos[0][0]},${alto - m.aba} Z`
  const marcas = [0, Math.floor(ultimo / 2), ultimo]

  const mover = (e: PointerEvent<SVGRectElement>) => {
    const caja = e.currentTarget.getBoundingClientRect()
    const rel = ((e.clientX - caja.left) / caja.width) * (ancho - m.izq - m.der)
    setActivo(Math.round((rel / (ancho - m.izq - m.der)) * ultimo))
  }
  const tecla = (e: KeyboardEvent<SVGSVGElement>) => {
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      e.preventDefault()
      setActivo((a) => Math.min(ultimo, Math.max(0, (a ?? ultimo) + (e.key === 'ArrowRight' ? 1 : -1))))
    }
  }
  const p = activo !== null ? serie[activo] : null

  return (
    <figure className="grafica-linea">
      <svg viewBox={`0 0 ${ancho} ${alto}`} width="100%" role="img" aria-labelledby={id} tabIndex={0} onKeyDown={tecla} onFocus={() => setActivo(ultimo)} onBlur={() => setActivo(null)}>
        <title id={id}>{etiqueta}</title>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={m.izq} x2={ancho - m.der} y1={y(t)} y2={y(t)} stroke={REJILLA} strokeWidth={1} />
            <text x={m.izq - 6} y={y(t)} dy="0.32em" textAnchor="end" className="eje">{dineroCorto(t)}</text>
          </g>
        ))}
        {marcas.map((i) => (
          <text key={i} x={x(i)} y={alto - 6} textAnchor={i === 0 ? 'start' : i === ultimo ? 'end' : 'middle'} className="eje">{fechaCorta(serie[i].dia)}</text>
        ))}
        <path d={area} fill={TINTA} opacity={0.1} />
        <path d={linea} fill="none" stroke={TINTA} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={puntos[ultimo][0]} cy={puntos[ultimo][1]} r={4} fill={TINTA} stroke="#fff" strokeWidth={2} />
        <text x={puntos[ultimo][0] + 8} y={puntos[ultimo][1]} dy="0.32em" className="valor-extremo">{dineroCorto(serie[ultimo].valor)}</text>
        {activo !== null && (
          <g pointerEvents="none">
            <line x1={puntos[activo][0]} x2={puntos[activo][0]} y1={m.arr} y2={alto - m.aba} stroke={TINTA} strokeWidth={1} />
            <circle cx={puntos[activo][0]} cy={puntos[activo][1]} r={4} fill={TINTA} stroke="#fff" strokeWidth={2} />
          </g>
        )}
        <rect x={m.izq} y={0} width={ancho - m.izq - m.der} height={alto - m.aba} fill="transparent" onPointerMove={mover} onPointerLeave={() => setActivo(null)} />
      </svg>
      {p && (
        <div className="grafica-tip" style={{ left: `${(puntos[activo!][0] / ancho) * 100}%` }} aria-live="polite">
          <strong>{dinero(p.valor)}</strong>
          <span>{fechaCorta(p.dia)}</span>
        </div>
      )}
    </figure>
  )
}

/** Barras horizontales de una serie, con el valor en la punta. */
export function BarrasH({ filas, formato, etiqueta }: { filas: Array<{ clave: string; nombre: string; valor: number }>; formato: (v: number) => string; etiqueta: string }) {
  const [activa, setActiva] = useState<string | null>(null)
  const max = Math.max(...filas.map((f) => f.valor), 1)
  const total = filas.reduce((a, f) => a + f.valor, 0)
  return (
    <div className="barras" role="list" aria-label={etiqueta}>
      {filas.map((f) => (
        <div
          key={f.clave}
          role="listitem"
          className="barra-fila"
          tabIndex={0}
          data-activa={activa === f.clave}
          onPointerEnter={() => setActiva(f.clave)}
          onPointerLeave={() => setActiva(null)}
          onFocus={() => setActiva(f.clave)}
          onBlur={() => setActiva(null)}
          aria-label={`${f.nombre}: ${formato(f.valor)}`}
        >
          <span className="nombre">{f.nombre}</span>
          <span className="pista">
            <span className="relleno" style={{ width: `${Math.max((f.valor / max) * 100, 0.5)}%` }} />
            {activa === f.clave && (
              <span className="grafica-tip barra-tip" style={{ left: `${Math.min((f.valor / max) * 100, 88)}%` }}>
                <strong>{formato(f.valor)}</strong>
                <span>{f.nombre} · {total ? Math.round((f.valor / total) * 100) : 0} % del total</span>
              </span>
            )}
          </span>
          <span className="valor">{formato(f.valor)}</span>
        </div>
      ))}
    </div>
  )
}
