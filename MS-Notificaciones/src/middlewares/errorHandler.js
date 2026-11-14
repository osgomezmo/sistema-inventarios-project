const { AppError } = require('../utils/errors');

/**
 * Middleware para rutas no encontradas (404).
 * Genera un AppError canónico y lo envía al errorHandler.
 */
function notFoundHandler(req, res, next) {
  next(new AppError(404, 'RUTA_NO_ENCONTRADA', 'Ruta no encontrada'));
}

/**
 * Middleware global de manejo de errores (4 parámetros).
 * Captura excepciones controladas (AppError) y no controladas,
 * formateando la respuesta JSON según el estándar de la arquitectura:
 * {
 *   "error": {
 *     "codigo": "...",
 *     "mensaje": "...",
 *     "detalles": null | object
 *   }
 * }
 */
// eslint-disable-next-line no-unused-vars
function errorHandler(err, req, res, next) {
  let statusCode = 500;
  let codigo = 'ERROR_INTERNO';
  let mensaje = 'Ocurrió un error interno en el servidor';
  let detalles = null;

  if (err instanceof AppError) {
    statusCode = err.statusCode || 500;
    codigo = err.codigo || 'ERROR';
    mensaje = err.mensaje;
    detalles = err.detalles;
  } else if (err && typeof err === 'object') {
    statusCode = err.statusCode || err.status || 500;
    codigo = err.codigo || 'ERROR_INTERNO';
    mensaje = err.message || mensaje;
    detalles = err.detalles || null;
  }

  res.status(statusCode).json({
    error: {
      codigo,
      mensaje,
      detalles,
    },
  });
}

module.exports = {
  notFoundHandler,
  errorHandler,
};
