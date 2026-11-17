class AppError extends Error {
  constructor(statusCode, codigo, mensaje, detalles = null) {
    super(mensaje);
    this.name = 'AppError';
    this.statusCode = statusCode;
    this.codigo = codigo;
    this.mensaje = mensaje;
    this.detalles = detalles;
    Error.captureStackTrace(this, this.constructor);
  }
}

module.exports = { AppError };
