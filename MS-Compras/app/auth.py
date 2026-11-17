"""Autenticacion interna servicio-a-servicio, roles de usuario y trazabilidad."""

from functools import wraps
import hmac
import uuid

from flask import current_app, g, request

from app.config import ConfigCompras
from app.errors import ErrorAPI

ROLES_PERMITIDOS = {"admin", "jefe_bodega", "compras", "gerente"}
RUTAS_PUBLICAS = {"/health", "/health/ready"}


def normalizar_rol(rol_bruto: str) -> str:
    """Normaliza alias comunes hacia los roles oficiales del sistema."""
    limpio = (rol_bruto or "").strip().lower()
    if limpio in {"jefe", "jefe_de_bodega", "bodega"}:
        return "jefe_bodega"
    return limpio


def registrar_hooks_seguridad(app) -> None:
    """Registra hooks de correlacion y validacion de headers de servicio."""

    @app.before_request
    def validar_peticion_interna():
        correlacion = (request.headers.get("X-Correlation-Id") or "").strip()
        g.correlation_id = correlacion or str(uuid.uuid4())

        if request.path in RUTAS_PUBLICAS or request.method == "OPTIONS":
            return None

        config: ConfigCompras = current_app.config["COMPRAS_CONFIG"]
        if not config.service_token:
            raise ErrorAPI(
                503,
                "SERVICIO_NO_DISPONIBLE",
                "SERVICE_TOKEN no configurado en el servicio.",
            )

        auth_header = request.headers.get("Authorization") or ""
        if not auth_header.startswith("Bearer "):
            raise ErrorAPI(
                401,
                "NO_AUTENTICADO",
                "Token de servicio requerido en header Authorization.",
            )

        token_recibido = auth_header[7:].strip()
        if not token_recibido or not hmac.compare_digest(
            token_recibido.encode("utf-8"),
            config.service_token.encode("utf-8"),
        ):
            raise ErrorAPI(
                401,
                "NO_AUTENTICADO",
                "Token de servicio invalido.",
            )

        user_id_raw = (request.headers.get("X-User-Id") or "").strip()
        try:
            user_id = int(user_id_raw)
        except ValueError as exc:
            raise ErrorAPI(
                401,
                "NO_AUTENTICADO",
                "Header X-User-Id requerido y debe ser entero positivo.",
            ) from exc

        if user_id <= 0:
            raise ErrorAPI(
                401,
                "NO_AUTENTICADO",
                "Header X-User-Id debe ser mayor que cero.",
            )

        rol = normalizar_rol(request.headers.get("X-User-Role") or "")
        if rol not in ROLES_PERMITIDOS:
            raise ErrorAPI(
                403,
                "NO_AUTORIZADO",
                "Header X-User-Role ausente o no reconocido.",
                {"rol": rol},
            )

        g.usuario_id = user_id
        g.usuario_rol = rol
        return None

    @app.after_request
    def adjuntar_correlation_id(response):
        correlacion = getattr(g, "correlation_id", None)
        if correlacion:
            response.headers["X-Correlation-Id"] = correlacion
        return response


def requiere_roles(*roles: str):
    """Decorador para exigir que el rol del usuario pertenezca al conjunto permitido."""
    permitidos = {normalizar_rol(r) for r in roles}

    def decorador(fn):
        @wraps(fn)
        def envoltura(*args, **kwargs):
            rol_actual = getattr(g, "usuario_rol", "")
            if rol_actual not in permitidos:
                raise ErrorAPI(
                    403,
                    "NO_AUTORIZADO",
                    "No tienes permisos para ejecutar esta operacion.",
                    {"roles_requeridos": sorted(permitidos), "rol_actual": rol_actual},
                )
            return fn(*args, **kwargs)

        return envoltura

    return decorador
