const { AppError } = require('../utils/errors');
const { normalizarRol } = require('../utils/roles');

/**
 * Middleware de autenticación interna entre servicios.
 * Valida que la petición contenga el token de servicio (SERVICE_TOKEN)
 * enviado por el API Gateway u otros microservicios autorizados.
 *
 * Además, extrae las cabeceras de contexto de usuario (X-User-Id y X-User-Role)
 * y las inyecta normalizadas en req.usuario.
 */
function authMiddleware(req, res, next) {
  const authHeader = req.header('Authorization');

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return next(new AppError(401, 'NO_AUTORIZADO', 'Token de servicio inválido o ausente'));
  }

  const token = authHeader.substring(7).trim();
  const serviceToken = process.env.SERVICE_TOKEN;

  if (!serviceToken || token !== serviceToken) {
    return next(new AppError(401, 'NO_AUTORIZADO', 'Token de servicio inválido o ausente'));
  }

  const rawUserId = req.header('X-User-Id');
  const rawUserRole = req.header('X-User-Role');

  req.usuario = {
    id: rawUserId || null,
    rol: normalizarRol(rawUserRole),
  };

  next();
}

module.exports = authMiddleware;
