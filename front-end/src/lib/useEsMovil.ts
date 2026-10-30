import { useEffect, useState } from 'react'

const CONSULTA = '(max-width: 760px)'

/** true en pantallas angostas (el mismo corte que usan los estilos). */
export function useEsMovil(): boolean {
  const [movil, setMovil] = useState(() => typeof matchMedia === 'function' && matchMedia(CONSULTA).matches)
  useEffect(() => {
    if (typeof matchMedia !== 'function') return
    const m = matchMedia(CONSULTA)
    const cambio = () => setMovil(m.matches)
    m.addEventListener('change', cambio)
    return () => m.removeEventListener('change', cambio)
  }, [])
  return movil
}
