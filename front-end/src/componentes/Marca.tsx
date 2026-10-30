// La «E» de Estiba es una estiba vista de lado y girada: la tabla superior queda vertical
// y los tres tacos que la separan del piso son los brazos de la letra.
export function LogoEstiba({ tamano = 30, color = 'currentColor' }: { tamano?: number; color?: string }) {
  return (
    <svg width={tamano} height={tamano} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect x="4" y="3" width="7" height="26" rx="1" fill={color} />
      <rect x="11" y="3" width="17" height="6.5" rx="1" fill={color} />
      <rect x="11" y="12.75" width="13" height="6.5" rx="1" fill={color} />
      <rect x="11" y="22.5" width="17" height="6.5" rx="1" fill={color} />
    </svg>
  )
}

export function Marca({ conNombre = true }: { conNombre?: boolean }) {
  return (
    <>
      <LogoEstiba />
      {conNombre && <span>Estiba</span>}
    </>
  )
}
