import { useCallback, useEffect, useState } from 'react'

export interface Consulta<T> {
  datos: T | undefined
  error: Error | undefined
  cargando: boolean
  recargar: () => void
}

/** Ejecuta una llamada a la API y expone sus estados de carga, error y datos. */
export function useConsulta<T>(llamada: () => Promise<T>, dependencias: unknown[]): Consulta<T> {
  const [datos, setDatos] = useState<T>()
  const [error, setError] = useState<Error>()
  const [cargando, setCargando] = useState(true)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let vigente = true
    setCargando(true)
    setError(undefined)
    llamada()
      .then((d) => { if (vigente) setDatos(d) })
      .catch((e: Error) => { if (vigente) setError(e) })
      .finally(() => { if (vigente) setCargando(false) })
    return () => { vigente = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencias, version])

  const recargar = useCallback(() => setVersion((v) => v + 1), [])
  return { datos, error, cargando, recargar }
}
