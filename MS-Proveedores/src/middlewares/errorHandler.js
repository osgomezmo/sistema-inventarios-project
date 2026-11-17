const { AppError } = require('../utils/errors');

function notFoundHandler(req, res, next) {
  next(new AppError(404, 'NO_EXISTE', 'Ruta no encontrada.'));
}

// eslint-disable-next-line no-unused-vars
function errorHandler(err, req, res, next) {
  if (err && err.type === 'entity.parse.failed') {
    return res.status(400).json({
      error: {
        codigo: 'PETICION_INVALIDA',
        mensaje: 'El cuerpo JSON está mal formado.',
        detalles: null,
      },
    });
  }

  let statusCode = 500;
  let codigo = 'ERROR_INTERNO';
  let mensaje = 'Ocurrió un error interno en el servidor.';
  let detalles = null;

  if (err instanceof AppError) {
    statusCode = err.statusCode || 500;
    codigo = err.codigo || 'ERROR';
    mensaje = err.mensaje;
    detalles = err.detalles ?? null;
  } else if (err && typeof err === 'object') {
    statusCode = err.statusCode || err.status || 500;
    codigo = err.codigo || 'ERROR_INTERNO';
    mensaje = statusCode >= 500 ? mensaje : err.message || mensaje;
    detalles = err.detalles ?? null;
  }

  return res.status(statusCode).json({
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
