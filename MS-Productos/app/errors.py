from flask import current_app, jsonify
from werkzeug.exceptions import HTTPException

ERRORES_HTTP = {
    400: ("PETICION_INVALIDA", "La petición está mal formada."),
    401: ("NO_AUTENTICADO", "La petición no está autenticada."),
    403: ("SIN_PERMISO", "No tienes permiso para esta operación."),
    404: ("NO_EXISTE", "El recurso no existe."),
    405: ("METODO_NO_PERMITIDO", "El método no está permitido en esta ruta."),
    409: ("CONFLICTO", "La operación entra en conflicto con el estado actual."),
    422: ("VALIDACION", "Revisa los campos enviados."),
    500: ("ERROR_INTERNO", "Ocurrió un error interno."),
    503: ("SERVICIO_NO_DISPONIBLE", "Un servicio del que depende no responde."),
}


class ApiError(Exception):
    def __init__(self, codigo, mensaje, status, detalles=None):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.status = status
        self.detalles = detalles


def respuesta_de_error(codigo, mensaje, status, detalles=None):
    cuerpo = {"error": {"codigo": codigo, "mensaje": mensaje, "detalles": detalles or {}}}
    return jsonify(cuerpo), status


def registrar_manejadores_de_error(app):
    @app.errorhandler(ApiError)
    def manejar_api_error(error):
        return respuesta_de_error(error.codigo, error.mensaje, error.status, error.detalles)

    @app.errorhandler(HTTPException)
    def manejar_error_http(error):
        codigo, mensaje = ERRORES_HTTP.get(
            error.code, ("ERROR_HTTP", "La petición no se pudo procesar.")
        )
        respuesta, status = respuesta_de_error(codigo, mensaje, error.code)
        metodos_validos = getattr(error, "valid_methods", None)
        if metodos_validos:
            respuesta.headers["Allow"] = ", ".join(metodos_validos)
        return respuesta, status

    @app.errorhandler(Exception)
    def manejar_error_inesperado(error):
        current_app.logger.exception("Error no controlado", exc_info=error)
        codigo, mensaje = ERRORES_HTTP[500]
        return respuesta_de_error(codigo, mensaje, 500)
