"""Excepciones de dominio y formato uniforme de errores HTTP."""

from typing import Any

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class ErrorAPI(Exception):
    """Error controlado serializable en el contrato estandar del sistema."""

    def __init__(
        self,
        status_code: int,
        codigo: str,
        mensaje: str,
        detalles: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.status_code = status_code
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalles = detalles or {}


def registrar_manejadores_error(app: Flask) -> None:
    """Registra los manejadores globales de excepciones en la app Flask."""

    @app.errorhandler(ErrorAPI)
    def manejar_error_api(err: ErrorAPI):
        cuerpo = {
            "error": {
                "codigo": err.codigo,
                "mensaje": err.mensaje,
                "detalles": err.detalles,
            }
        }
        return jsonify(cuerpo), err.status_code

    @app.errorhandler(HTTPException)
    def manejar_error_http(err: HTTPException):
        codigo = "NO_EXISTE" if err.code == 404 else "ERROR_HTTP"
        cuerpo = {
            "error": {
                "codigo": codigo,
                "mensaje": err.description or "Error en la solicitud HTTP.",
                "detalles": {},
            }
        }
        return jsonify(cuerpo), err.code or 500

    @app.errorhandler(Exception)
    def manejar_error_inesperado(err: Exception):
        app.logger.exception("Error interno no controlado en ms-compras: %s", err)
        cuerpo = {
            "error": {
                "codigo": "ERROR_INTERNO",
                "mensaje": "Ocurrio un error interno en el servicio.",
                "detalles": {},
            }
        }
        return jsonify(cuerpo), 500
