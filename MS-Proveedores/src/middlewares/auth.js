const crypto = require('crypto');
const { config } = require('../config/env');
const { AppError } = require('../utils/errors');
const { normalizarRol } = require('../utils/roles');

function tokensIguales(recibido, esperado) {
  if (!recibido || !esperado) return false;
  const bufA = Buffer.from(recibido, 'utf8');
  const bufB = Buffer.from(esperado, 'utf8');
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

/**
 * Valida Authorization: Bearer <SERVICE_TOKEN> en todas las rutas protegidas
 * e inyecta req.usuario con X-User-Id y X-User-Role normalizado.
 */
function authMiddleware(req, res, next) {
  const authHeader = req.header('Authorization');

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return next(new AppError(401, 'NO_AUTENTICADO', 'Token de servicio ausente o inválido.'));
  }

  const token = authHeader.substring(7).trim();
  if (!tokensIguales(token, config.serviceToken)) {
    return next(new AppError(401, 'NO_AUTENTICADO', 'Token de servicio ausente o inválido.'));
  }

  const rawUserId = req.header('X-User-Id');
  const rawUserRole = req.header('X-User-Role');

  req.usuario = {
    id: rawUserId ? rawUserId.trim() : null,
    rol: normalizarRol(rawUserRole),
  };

  return next();
}

module.exports = authMiddleware;
