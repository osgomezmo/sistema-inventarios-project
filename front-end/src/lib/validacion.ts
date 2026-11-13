// Validación en el cliente. Revisa los datos antes de enviarlos para avisar al instante;
// el servidor (gateway y microservicios) vuelve a validar y responde 422 o 409 si algo se escapa.
import { useCallback, useState, type FocusEvent } from 'react'
import type { UnidadMedida } from '../api/types'

export type Errores = Record<string, string[]>
type Mensaje = string | null | false | undefined

const vacio = (v: string | undefined | null) => !v || v.trim() === ''

/** Convierte «12», «12,5» o «12.5» en número; null si no es un número válido. */
export function aNumero(v: string): number | null {
  const t = v.trim().replace(',', '.')
  if (!/^-?\d+(\.\d+)?$/.test(t)) return null
  return Number(t)
}

const decimalesDe = (v: string) => v.trim().replace(',', '.').split('.')[1]?.length ?? 0

export const decimalesPorUnidad = (u: UnidadMedida) => (u === 'UNIDAD' ? 0 : 3)

export const reglas = {
  requerido: (v: string | number | undefined | null, mensaje = 'Este dato es obligatorio.'): Mensaje =>
    (typeof v === 'number' ? !v : vacio(v)) && mensaje,

  largo: (v: string, min: number, max: number): Mensaje => {
    const n = v.trim().length
    if (n === 0) return null
    if (n < min) return `Escribe al menos ${min} caracteres.`
    if (n > max) return `Máximo ${max} caracteres; llevas ${n}.`
    return null
  },

  email: (v: string): Mensaje =>
    !vacio(v) && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim()) && 'Escribe un correo válido, por ejemplo nombre@empresa.com.',

  patron: (v: string, re: RegExp, mensaje: string): Mensaje => !vacio(v) && !re.test(v.trim()) && mensaje,

  /** Número con límites y decimales; los mensajes dicen cómo corregirlo. */
  numero: (v: string, o: { requerido?: boolean; mensajeVacio?: string; decimales?: number; mayorQueCero?: boolean; min?: number; max?: number; mensajeMax?: string }): Mensaje => {
    if (vacio(v)) return o.requerido ? (o.mensajeVacio ?? 'Escribe una cantidad.') : null
    const n = aNumero(v)
    if (n === null) return 'Escribe solo números; usa coma para los decimales.'
    if (o.decimales !== undefined && decimalesDe(v) > o.decimales) return o.decimales === 0 ? 'Esta unidad no admite decimales.' : `Máximo ${o.decimales} decimales.`
    if (o.mayorQueCero && n <= 0) return 'Debe ser mayor que cero.'
    if (o.min !== undefined && n < o.min) return `No puede ser menor que ${o.min}.`
    if (o.max !== undefined && n > o.max) return o.mensajeMax ?? `No puede ser mayor que ${o.max}.`
    return null
  },

  /** NIT colombiano con dígito de verificación (DIAN): 900.123.456-7 o 900123456-7. */
  nit: (v: string): Mensaje => {
    if (vacio(v)) return null
    const m = /^(\d{1,3}(?:\.?\d{3}){2,3})-(\d)$/.exec(v.trim())
    if (!m) return 'Usa el formato 900.123.456-7: número, guion y dígito de verificación.'
    const base = m[1].replace(/\./g, '')
    const pesos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    const suma = [...base].reverse().reduce((a, d, i) => a + Number(d) * pesos[i], 0)
    const r = suma % 11
    const dv = r > 1 ? 11 - r : r
    return dv !== Number(m[2]) && `El dígito de verificación no corresponde: para ${m[1]} debería ser ${dv}.`
  },

  telefono: (v: string): Mensaje => {
    if (vacio(v)) return null
    if (!/^\+?[\d\s()-]+$/.test(v.trim())) return 'Usa solo números, espacios, guiones o el prefijo +57.'
    const digitos = v.replace(/\D/g, '').length
    return (digitos < 7 || digitos > 12) && 'Un teléfono tiene entre 7 y 12 dígitos.'
  },

  password: (v: string): Mensaje => {
    if (vacio(v)) return null
    if (v.length < 8) return 'Usa al menos 8 caracteres.'
    if (!/[A-Za-zÁÉÍÓÚáéíóúÑñ]/.test(v) || !/\d/.test(v)) return 'Combina letras y números.'
    return null
  },

  nombrePersona: (v: string): Mensaje =>
    !vacio(v) && !/^[A-Za-zÁÉÍÓÚáéíóúÑñÜü' .-]+$/.test(v.trim()) && 'Usa solo letras y espacios.',

  sku: (v: string): Mensaje => !vacio(v) && !/^[A-Za-z]{3}-\d{4}$/.test(v.trim()) && 'Usa tres letras, guion y cuatro números, por ejemplo LAC-0210.',

  codigoBodega: (v: string): Mensaje => !vacio(v) && !/^[A-Za-z]\d{1,3}$/.test(v.trim()) && 'Usa una letra y hasta tres números, por ejemplo B5.',

  facturaPos: (v: string): Mensaje => !vacio(v) && !/^[A-Za-z0-9-]{4,30}$/.test(v.trim()) && 'Usa letras, números y guiones, por ejemplo FV-POS-0019802.',

  rangoFechas: (desde: string, hasta: string): Mensaje => !vacio(desde) && !vacio(hasta) && desde > hasta && 'La fecha final debe ser igual o posterior a la inicial.',
}

/** Arma el objeto de errores: por campo, el primer mensaje que falle. */
export function validar(campos: Record<string, Mensaje[]>): Errores {
  const errores: Errores = {}
  for (const [campo, mensajes] of Object.entries(campos)) {
    const primero = mensajes.find((m): m is string => typeof m === 'string' && m.length > 0)
    if (primero) errores[campo] = [primero]
  }
  return errores
}

/**
 * Controla cuándo se ven los errores: el de cada campo al salir de él (atributo name) y
 * todos al intentar guardar. comprobar() devuelve false y lleva el foco al primer error.
 */
export function useValidacion(errores: Errores) {
  const [intentado, setIntentado] = useState(false)
  const [tocados, setTocados] = useState<Set<string>>(() => new Set())

  const visibles: Errores = intentado ? errores : Object.fromEntries(Object.entries(errores).filter(([k]) => tocados.has(k)))

  const alSalir = useCallback((e: FocusEvent<HTMLElement>) => {
    const nombre = (e.target as HTMLInputElement).name
    if (nombre) setTocados((t) => (t.has(nombre) ? t : new Set(t).add(nombre)))
  }, [])

  function comprobar(formulario?: HTMLFormElement | null): boolean {
    setIntentado(true)
    const valido = Object.keys(errores).length === 0
    if (!valido) setTimeout(() => formulario?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus(), 0)
    return valido
  }

  const reiniciar = useCallback(() => { setIntentado(false); setTocados(new Set()) }, [])

  return { visibles, alSalir, comprobar, reiniciar }
}
