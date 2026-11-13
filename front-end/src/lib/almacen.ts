// Acceso a localStorage que nunca rompe la página (modo privado, almacenamiento bloqueado).
export function leer<T>(clave: string): T | null {
  try {
    const crudo = localStorage.getItem(clave)
    return crudo ? (JSON.parse(crudo) as T) : null
  } catch {
    return null
  }
}

export function guardar(clave: string, valor: unknown): void {
  try {
    if (valor === null) localStorage.removeItem(clave)
    else localStorage.setItem(clave, JSON.stringify(valor))
  } catch {
    /* sin almacenamiento: la sesión vive solo en memoria */
  }
}
