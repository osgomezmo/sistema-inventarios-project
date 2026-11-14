const ROLES_VALIDOS = ['admin', 'jefe_bodega', 'compras', 'gerente'];

/**
 * Normaliza cualquier variante de los roles definidos en el sistema:
 * - 'Administrador' / 'Admin' -> 'admin'
 * - 'Jefe de bodega' / 'Jefe' -> 'jefe_bodega'
 * - 'Compras' -> 'compras'
 * - 'Gerente' -> 'gerente'
 */
function normalizarRol(rawRol) {
  if (!rawRol || typeof rawRol !== 'string') {
    return null;
  }

  const limpio = rawRol.trim().toLowerCase();

  if (limpio === 'administrador' || limpio === 'admin') {
    return 'admin';
  }
  if (
    limpio === 'jefe de bodega' ||
    limpio === 'jefe' ||
    limpio === 'jefe_bodega' ||
    limpio === 'jefebodega'
  ) {
    return 'jefe_bodega';
  }
  if (limpio === 'compras') {
    return 'compras';
  }
  if (limpio === 'gerente') {
    return 'gerente';
  }

  return limpio;
}

module.exports = {
  normalizarRol,
  ROLES_VALIDOS,
};
