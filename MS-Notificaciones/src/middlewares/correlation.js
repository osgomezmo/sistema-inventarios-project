const { v4: uuidv4 } = require('uuid');

/**
 * Middleware para capturar o generar el X-Correlation-Id
 * y propagarlo tanto en el objeto req como en las cabeceras de respuesta HTTP.
 */
function correlationMiddleware(req, res, next) {
  const correlationId = req.header('X-Correlation-Id') || uuidv4();
  req.correlationId = correlationId;
  res.setHeader('X-Correlation-Id', correlationId);
  next();
}

module.exports = correlationMiddleware;
