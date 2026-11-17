"""Cliente HTTP sincrono para validar proveedores en ms-proveedores."""

from typing import Any

from flask import current_app, g
import requests

from app.config import ConfigCompras
from app.errors import ErrorAPI


def validar_proveedor_activo(id_proveedor: int) -> dict[str, Any]:
    """Consulta ms-proveedores y verifica que el proveedor exista y este activo."""
    config: ConfigCompras = current_app.config["COMPRAS_CONFIG"]
    url = f"{config.proveedores_url}/proveedores/{id_proveedor}"

    headers = {
        "Authorization": f"Bearer {config.service_token}",
        "X-User-Id": str(getattr(g, "usuario_id", 0)),
        "X-User-Role": str(getattr(g, "usuario_rol", "compras")),
        "X-Correlation-Id": str(getattr(g, "correlation_id", "")),
    }

    try:
        respuesta = requests.get(
            url,
            headers=headers,
            timeout=config.proveedores_timeout_seconds,
        )
    except requests.RequestException as exc:
        raise ErrorAPI(
            503,
            "SERVICIO_NO_DISPONIBLE",
            "ms-proveedores no disponible para validar el proveedor.",
            {"detalle": str(exc)},
        ) from exc

    if respuesta.status_code == 404:
        raise ErrorAPI(
            422,
            "PROVEEDOR_NO_EXISTE",
            f"El proveedor {id_proveedor} no existe en ms-proveedores.",
            {"id_proveedor": id_proveedor},
        )

    if respuesta.status_code >= 500:
        raise ErrorAPI(
            503,
            "SERVICIO_NO_DISPONIBLE",
            "ms-proveedores respondio con error interno al validar el proveedor.",
            {"status": respuesta.status_code},
        )

    if respuesta.status_code != 200:
        raise ErrorAPI(
            503,
            "SERVICIO_NO_DISPONIBLE",
            "Respuesta inesperada de ms-proveedores al validar el proveedor.",
            {"status": respuesta.status_code},
        )

    try:
        datos = respuesta.json()
    except ValueError as exc:
        raise ErrorAPI(
            503,
            "SERVICIO_NO_DISPONIBLE",
            "Respuesta JSON invalida desde ms-proveedores.",
        ) from exc

    proveedor = datos.get("data") if isinstance(datos, dict) and "data" in datos else datos
    if not isinstance(proveedor, dict):
        raise ErrorAPI(
            503,
            "SERVICIO_NO_DISPONIBLE",
            "Estructura de respuesta inesperada desde ms-proveedores.",
        )

    estado = proveedor.get("estado")
    if estado is not None:
        esta_activo = str(estado).strip().upper() == "ACTIVO"
    elif "activo" in proveedor:
        esta_activo = bool(proveedor.get("activo"))
    else:
        esta_activo = False

    if not esta_activo:
        raise ErrorAPI(
            422,
            "PROVEEDOR_INACTIVO",
            f"El proveedor {id_proveedor} esta inactivo.",
            {"id_proveedor": id_proveedor, "estado": estado},
        )

    return proveedor
