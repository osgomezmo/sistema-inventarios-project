// Confirmaciones breves después de una operación («Movimiento MOV-004776 registrado»).
import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { CircleCheck } from 'lucide-react'

interface Aviso { id: number; texto: string; enlace?: { a: string; texto: string } }

const Contexto = createContext<((texto: string, enlace?: Aviso['enlace']) => void) | null>(null)

export function ProveedorAvisos({ children }: { children: ReactNode }) {
  const [avisos, setAvisos] = useState<Aviso[]>([])
  const avisar = useCallback((texto: string, enlace?: Aviso['enlace']) => {
    const id = Date.now() + Math.random()
    setAvisos((a) => [...a, { id, texto, enlace }])
    setTimeout(() => setAvisos((a) => a.filter((x) => x.id !== id)), 6000)
  }, [])
  return (
    <Contexto.Provider value={avisar}>
      {children}
      <div className="toast-zona" role="status" aria-live="polite">
        {avisos.map((a) => (
          <div className="toast" key={a.id}>
            <CircleCheck size={22} aria-hidden />
            <span>{a.texto}</span>
            {a.enlace && <Link to={a.enlace.a}>{a.enlace.texto}</Link>}
          </div>
        ))}
      </div>
    </Contexto.Provider>
  )
}

export function useAvisos() {
  const c = useContext(Contexto)
  if (!c) throw new Error('useAvisos debe usarse dentro de ProveedorAvisos')
  return c
}
