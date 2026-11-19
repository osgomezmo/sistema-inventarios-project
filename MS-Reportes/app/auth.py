import hmac
import uuid

from flask import g, request

from app.errors import ApiError

RUTAS_PUBLICAS = {"/health"}
TOKEN_DE_EJEMPLO = "cambia-este-token"


def registrar_autenticacion(app):
    token = app.config.get("SERVICE_TOKEN")
    if not token:
        raise RuntimeError(
            "SERVICE_TOKEN no está definido: configúralo en el entorno o en el archivo .env."
        )
    if token == TOKEN_DE_EJEMPLO:
        raise RuntimeError(
            "SERVICE_TOKEN conserva el valor de ejemplo de .env.example: reemplázalo por un token aleatorio."
        )
    esperado = token.encode()

    @app.before_request
    def capturar_contexto_y_autenticar():
        g.correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        g.user_id = request.headers.get("X-User-Id")
        g.user_role = request.headers.get("X-User-Role")

        if request.path in RUTAS_PUBLICAS:
            return None

        esquema, _, recibido = request.headers.get("Authorization", "").partition(" ")
        if esquema != "Bearer" or not hmac.compare_digest(recibido.encode(), esperado):
            raise ApiError("NO_AUTENTICADO", "Token de servicio ausente o inválido.", 401)
        return None

    @app.after_request
    def propagar_encabezados(response):
        if hasattr(g, "correlation_id") and g.correlation_id:
            response.headers["X-Correlation-Id"] = g.correlation_id
        return response
