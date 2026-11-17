// Transporte hacia el API Gateway. Toda petición va a /api (mismo origen: en el
// contenedor la reenvía Nginx y en desarrollo el proxy de Vite), con el token
// personal de Sanctum en Authorization: Bearer. El gateway valida el token y el
// permiso del rol y llama al microservicio con su propio token de servicio.
import type { ErrorApi, Paginado } from './types'

const BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/+$/, '')

export class ApiError extends Error {
  status: number
  cuerpo: ErrorApi
  constructor(status: number, codigo: string, mensaje: string, detalles?: Record<string, string[]>) {
    super(mensaje)
    this.name = 'ApiError'
    this.status = status
    this.cuerpo = { error: { codigo, mensaje, detalles } }
  }
}

// ---------- Sesión ----------

let token: string | null = null
let alExpirar: (() => void) | null = null

/** Sesion.tsx registra aquí el token vigente y qué hacer si el gateway lo rechaza. */
export function configurarSesion(nuevo: string | null, expirar?: () => void) {
  token = nuevo
  if (expirar) alExpirar = expirar
}

// ---------- Peticiones ----------

type Valor = string | number | boolean | null | undefined
export type Consulta = Record<string, Valor>

interface Opciones {
  query?: Consulta
  cuerpo?: unknown
  /** Login: sin token y sin tratar el 401 como sesión vencida. */
  sinSesion?: boolean
}

function armarUrl(ruta: string, query?: Consulta): string {
  const params = new URLSearchParams()
  for (const [clave, valor] of Object.entries(query ?? {})) {
    if (valor === undefined || valor === null || valor === '') continue
    params.set(clave, String(valor))
  }
  const texto = params.toString()
  return `${BASE}${ruta}${texto ? `?${texto}` : ''}`
}

const POR_ESTADO: Record<number, [string, string]> = {
  400: ['PETICION_INVALIDA', 'La petición está mal formada.'],
  401: ['NO_AUTENTICADO', 'Tu sesión terminó; vuelve a ingresar.'],
  403: ['SIN_PERMISO', 'Tu rol no tiene permiso para esta operación.'],
  404: ['NO_EXISTE', 'El recurso no existe.'],
  409: ['CONFLICTO', 'La operación entra en conflicto con el estado actual.'],
  422: ['VALIDACION', 'Revisa los campos enviados.'],
  429: ['DEMASIADAS_PETICIONES', 'Demasiados intentos; espera un momento.'],
  502: ['SERVICIO_NO_DISPONIBLE', 'El gateway no responde.'],
  503: ['SERVICIO_NO_DISPONIBLE', 'Un servicio del que depende la operación no responde.'],
  504: ['SERVICIO_NO_DISPONIBLE', 'El gateway tardó demasiado en responder.'],
}

/**
 * Los servicios no escriben igual los detalles: Laravel y Flask mandan listas por
 * campo, ms-compras a veces un valor suelto y ms-notificaciones null. Solo se
 * conservan los mensajes de texto por campo, que es lo que muestran los formularios.
 */
function detallesDe(valor: unknown): Record<string, string[]> | undefined {
  if (!valor || typeof valor !== 'object' || Array.isArray(valor)) return undefined
  const detalles: Record<string, string[]> = {}
  for (const [campo, v] of Object.entries(valor)) {
    if (Array.isArray(v)) {
      const textos = v.filter((x): x is string => typeof x === 'string')
      if (textos.length) detalles[campo] = textos
    } else if (typeof v === 'string') {
      detalles[campo] = [v]
    }
  }
  return Object.keys(detalles).length ? detalles : undefined
}

let revisando: Promise<void> | null = null

/**
 * Un 401 puede venir del gateway (token de Sanctum vencido o revocado) o de un
 * microservicio que no aceptó el token de servicio. Se pregunta a /auth/me: si el
 * gateway también lo rechaza, la sesión terminó; si no, es un error de configuración.
 */
async function sesionSigueValida(): Promise<boolean> {
  try {
    const r = await fetch(armarUrl('/auth/me'), { headers: { Accept: 'application/json', Authorization: `Bearer ${token}` } })
    return r.status !== 401
  } catch {
    return true
  }
}

async function tratar401(): Promise<ApiError> {
  if (await sesionSigueValida()) {
    return new ApiError(502, 'TOKEN_SERVICIO', 'Un microservicio rechazó la credencial interna del gateway. Revisa que SERVICE_TOKEN sea igual en el gateway y en los servicios.')
  }
  revisando ??= Promise.resolve().then(() => { alExpirar?.() }).finally(() => { revisando = null })
  await revisando
  return new ApiError(401, 'NO_AUTENTICADO', POR_ESTADO[401][1])
}

export async function pedir<T>(metodo: 'GET' | 'POST' | 'PUT' | 'DELETE', ruta: string, opciones: Opciones = {}): Promise<T> {
  const { query, cuerpo, sinSesion } = opciones
  const cabeceras: Record<string, string> = { Accept: 'application/json' }
  if (cuerpo !== undefined) cabeceras['Content-Type'] = 'application/json'
  if (token && !sinSesion) cabeceras.Authorization = `Bearer ${token}`

  let respuesta: Response
  try {
    respuesta = await fetch(armarUrl(ruta, query), {
      method: metodo,
      headers: cabeceras,
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    })
  } catch {
    throw new ApiError(0, 'SIN_CONEXION', 'No hay conexión con el servidor. Revisa la red e inténtalo de nuevo.')
  }

  if (respuesta.status === 204) return undefined as T
  const texto = await respuesta.text()
  let datos: unknown = null
  if (texto) {
    try { datos = JSON.parse(texto) } catch { datos = null }
  }
  if (respuesta.ok) return datos as T

  if (respuesta.status === 401 && token && !sinSesion) throw await tratar401()
  const error = (datos as Partial<ErrorApi> | null)?.error
  const [codigo, mensaje] = POR_ESTADO[respuesta.status] ?? ['ERROR_HTTP', 'La petición no se pudo procesar.']
  throw new ApiError(respuesta.status, error?.codigo ?? codigo, error?.mensaje ?? mensaje, detallesDe(error?.detalles))
}

/** Recorre todas las páginas de un listado (per_page máximo de 100 en todos los servicios). */
export async function todas<T>(ruta: string, query: Consulta = {}): Promise<T[]> {
  const filas: T[] = []
  for (let page = 1; page <= 200; page++) {
    const r = await pedir<Paginado<T>>('GET', ruta, { query: { ...query, page, per_page: 100 } })
    filas.push(...r.data)
    if (r.data.length === 0 || filas.length >= r.meta.total) break
  }
  return filas
}
