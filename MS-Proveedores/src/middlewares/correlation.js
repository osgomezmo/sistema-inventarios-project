const { v4: uuidv4 } = require('uuid');

/**
 * Captura o genera X-Correlation-Id, lo propaga en la respuesta HTTP
 * y registra una línea de log estructurada en JSON sin exponer secretos.
 */
function correlationMiddleware(req, res, next) {
  const inicio = process.hrtime.bigint();
  const correlationId = (req.header('X-Correlation-Id') || '').trim() || uuidv4();

  req.correlationId = correlationId;
  res.setHeader('X-Correlation-Id', correlationId);

  res.on('finish', () => {
    const duracionMs = Number(process.hrtime.bigint() - inicio) / 1e6;
    const registro = {
      fecha: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
      servicio: 'ms-proveedores',
      nivel: res.statusCode >= 500 ? 'error' : res.statusCode >= 400 ? 'warn' : 'info',
      id_correlacion: correlationId,
      metodo: req.method,
      ruta: req.originalUrl,
      status: res.statusCode,
      duracion_ms: Math.round(duracionMs * 100) / 100,
      id_usuario: req.usuario ? req.usuario.id : null,
    };
    console.log(JSON.stringify(registro));
  });

  next();
}

module.exports = correlationMiddleware;
