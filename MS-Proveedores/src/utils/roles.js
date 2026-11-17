const { AppError } = require('./errors');

const ROLES_VALIDOS = ['admin', 'jefe_bodega', 'compras', 'gerente'];

/**
 * Normaliza las variantes de nombres de rol recibidas desde el API Gateway:
 * - 'Administrador' / 'Admin' / 'ADMINISTRADOR' -> 'admin'
 * - 'Jefe de bodega' / 'Jefe' / 'JEFE_BODEGA' -> 'jefe_bodega'
 * - 'Compras' / 'COMPRAS' -> 'compras'
 * - 'Gerente' / 'GERENTE' -> 'gerente'
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

/**
 * Middleware de autorización por rol.
 * Si permitirInterno es true, las llamadas internas con SERVICE_TOKEN válido
 * y sin X-User-Role están autorizadas; si viene X-User-Role, se valida.
 */
function requerirRoles(rolesPermitidos, { permitirInterno = false } = {}) {
  return (req, res, next) => {
    const rol = req.usuario ? req.usuario.rol : null;

    if (!rol) {
      if (permitirInterno) {
        return next();
      }
      return next(new AppError(403, 'SIN_PERMISO', 'No tienes permiso para realizar esta operación.'));
    }

    if (!ROLES_VALIDOS.includes(rol) || !rolesPermitidos.includes(rol)) {
      return next(new AppError(403, 'SIN_PERMISO', 'No tienes permiso para realizar esta operación.'));
    }

    return next();
  };
}

module.exports = {
  ROLES_VALIDOS,
  normalizarRol,
  requerirRoles,
};
