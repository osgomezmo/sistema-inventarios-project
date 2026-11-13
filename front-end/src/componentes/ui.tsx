import { cloneElement, isValidElement, type ReactElement, type ReactNode } from 'react'
import { ChevronLeft, ChevronRight, CircleAlert, Inbox, LoaderCircle, RotateCcw } from 'lucide-react'
import type { EstadoOrden, MetaPaginacion, Movimiento, Saldo, TipoMovimiento } from '../api/types'
import { ApiError } from '../api/cliente'
import { productoPorSku } from '../api/mock/maestros'
import { cantidad, nombreEstadoOrden, nombreTipo, numero } from '../lib/formato'

// ---------- Encabezado de página ----------

export function Encabezado({ titulo, codigo, descripcion, acciones, migas }: {
  titulo: ReactNode
  codigo?: string
  descripcion?: ReactNode
  acciones?: ReactNode
  migas?: ReactNode
}) {
  return (
    <header className="encabezado">
      <div className="encabezado-texto">
        {migas && <nav className="migas" aria-label="Ruta">{migas}</nav>}
        <h1>{titulo}{codigo && <span className="codigo">{codigo}</span>}</h1>
        {descripcion && <p>{descripcion}</p>}
      </div>
      {acciones && <div className="encabezado-acciones">{acciones}</div>}
    </header>
  )
}

// ---------- Estados de una consulta ----------

export function Cargando({ filas = 6, texto = 'Cargando' }: { filas?: number; texto?: string }) {
  return (
    <div className="esqueleto" aria-busy="true" aria-label={texto}>
      {Array.from({ length: filas }, (_, i) => <i key={i} />)}
    </div>
  )
}

export function Vacio({ titulo, children, accion, icono }: { titulo: string; children?: ReactNode; accion?: ReactNode; icono?: ReactNode }) {
  return (
    <div className="vacio">
      {icono ?? <Inbox size={40} aria-hidden />}
      <strong>{titulo}</strong>
      {children && <p>{children}</p>}
      {accion}
    </div>
  )
}

export function ErrorCaja({ error, reintentar }: { error: Error; reintentar?: () => void }) {
  const api = error instanceof ApiError ? error.cuerpo.error : null
  return (
    <div className="aviso aviso-error" role="alert">
      <CircleAlert size={22} aria-hidden />
      <div>
        <strong>{api ? tituloError(error as ApiError) : 'No se pudo cargar la información'}</strong>
        <p>{api?.mensaje ?? 'Revisa la conexión con el servidor e inténtalo de nuevo.'}</p>
      </div>
      {reintentar && <button type="button" className="btn btn-sm" onClick={reintentar}><RotateCcw size={16} aria-hidden />Reintentar</button>}
    </div>
  )
}

function tituloError(e: ApiError): string {
  switch (e.status) {
    case 401: return 'Tu sesión terminó'
    case 403: return 'No tienes permiso para esta acción'
    case 404: return 'No se encontró'
    case 409: return 'La operación no se puede hacer así'
    case 422: return 'Revisa los datos'
    case 503: return 'Un servicio no responde'
    default: return 'Ocurrió un error'
  }
}

/** Error corto para una celda de tabla (formularios con filas, como los ítems de una orden). */
export function ErrorCelda({ id, error }: { id: string; error?: string[] }) {
  if (!error?.length) return null
  return <span className="error-celda" id={id} role="alert"><CircleAlert size={14} aria-hidden />{error[0]}</span>
}

/** Errores por campo de una respuesta 422 o 409. */
export const erroresCampo = (e: unknown): Record<string, string[]> =>
  e instanceof ApiError ? e.cuerpo.error.detalles ?? {} : {}

// ---------- Paginación ----------

export function Paginacion({ meta, cambiar }: { meta: MetaPaginacion; cambiar: (pagina: number) => void }) {
  const desde = meta.total === 0 ? 0 : (meta.page - 1) * meta.per_page + 1
  const hasta = Math.min(meta.page * meta.per_page, meta.total)
  const ultima = Math.max(1, Math.ceil(meta.total / meta.per_page))
  return (
    <div className="paginacion">
      <span className="cifra">{numero(desde)}–{numero(hasta)} de {numero(meta.total)}</span>
      <div>
        <button type="button" className="btn btn-sm" disabled={meta.page <= 1} onClick={() => cambiar(meta.page - 1)}>
          <ChevronLeft size={18} aria-hidden />Anterior
        </button>
        <button type="button" className="btn btn-sm" disabled={meta.page >= ultima} onClick={() => cambiar(meta.page + 1)}>
          Siguiente<ChevronRight size={18} aria-hidden />
        </button>
      </div>
    </div>
  )
}

// ---------- Campos de formulario ----------

export function Campo({ id, etiqueta, error, ayuda, opcional, children }: {
  id: string
  etiqueta: string
  error?: string[]
  ayuda?: string
  opcional?: boolean
  children: ReactNode
}) {
  const conError = !!error?.length
  // El control recibe aria-invalid y queda ligado a su mensaje de error o de ayuda.
  const control = isValidElement(children)
    ? cloneElement(children as ReactElement<Record<string, unknown>>, {
        'aria-invalid': conError || undefined,
        'aria-describedby': conError ? `${id}-error` : ayuda ? `${id}-ayuda` : undefined,
      })
    : children
  return (
    <div className="campo" data-error={conError ? 'true' : undefined}>
      <label htmlFor={id}>{etiqueta}{opcional && <span className="opcional"> (opcional)</span>}</label>
      {control}
      {ayuda && !error?.length && <span className="ayuda" id={`${id}-ayuda`}>{ayuda}</span>}
      {conError && <span className="error-campo" id={`${id}-error`} role="alert"><CircleAlert size={16} aria-hidden />{error![0]}</span>}
    </div>
  )
}

export function BotonEnvio({ enviando, children, className = 'btn btn-pri' }: { enviando: boolean; children: ReactNode; className?: string }) {
  return (
    <button type="submit" className={className} disabled={enviando}>
      {enviando && <LoaderCircle size={18} className="girando" aria-hidden />}
      {enviando ? 'Guardando…' : children}
    </button>
  )
}

// ---------- Etiquetas de estado ----------

export function EtiquetaSaldo({ saldo }: { saldo: Pick<Saldo, 'cantidad' | 'stock_minimo'> }) {
  if (saldo.cantidad === 0) return <span className="tag tag-agotado">Agotado</span>
  if (saldo.cantidad <= saldo.stock_minimo) return <span className="tag tag-bajo">Stock bajo</span>
  return <span className="tag">Normal</span>
}

const claseOrden: Record<EstadoOrden, string> = {
  BORRADOR: 'tag tag-borrador',
  APROBADA: 'tag tag-pendiente',
  RECIBIDA_PARCIAL: 'tag tag-pendiente',
  RECIBIDA: 'tag tag-ok',
  ANULADA: 'tag tag-inactivo',
}
export const EtiquetaOrden = ({ estado }: { estado: EstadoOrden }) => <span className={claseOrden[estado]}>{nombreEstadoOrden[estado]}</span>

export const EtiquetaEstado = ({ estado }: { estado: 'ACTIVO' | 'INACTIVO' }) =>
  estado === 'ACTIVO' ? <span className="tag">Activo</span> : <span className="tag tag-inactivo">Inactivo</span>

export const TipoMov = ({ tipo }: { tipo: TipoMovimiento }) => <>{nombreTipo[tipo]}</>

const entradas: TipoMovimiento[] = ['ENTRADA_COMPRA', 'AJUSTE_POSITIVO', 'TRASLADO_ENTRADA', 'DEVOLUCION_CLIENTE']

/** Cantidad de un movimiento con signo: + entra, − sale; las mermas y daños en rojo. */
export function CantidadMov({ m }: { m: Pick<Movimiento, 'tipo' | 'cantidad' | 'sku'> }) {
  const p = productoPorSku.get(m.sku)!
  const entra = entradas.includes(m.tipo)
  const clase = entra ? 'mas' : m.tipo === 'AJUSTE_NEGATIVO' ? 'merma' : 'menos'
  return <span className={`${clase} cifra`}>{entra ? '+' : '−'}{cantidad(m.cantidad, p.unidad_medida)}</span>
}
