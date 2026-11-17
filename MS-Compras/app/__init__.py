"""Fabrica de aplicacion Flask para el microservicio ms-compras."""

from dataclasses import replace
from typing import Any

from flask import Flask
from mysql.connector import Error as MySQLError

from app.auth import registrar_hooks_seguridad
from app.config import cargar_configuracion
from app.db import inicializar_pool
from app.errors import registrar_manejadores_error
from app.json_provider import ProveedorJSONCompras
from app.routes import registrar_rutas


def crear_app(config_override: dict[str, Any] | None = None) -> Flask:
    """Construye y configura la instancia Flask de ms-compras."""
    config = cargar_configuracion()
    if config_override:
        config = replace(config, **config_override)

    app = Flask(__name__)
    app.json = ProveedorJSONCompras(app)
    app.config["COMPRAS_CONFIG"] = config
    app.config["JSON_SORT_KEYS"] = False

    try:
        inicializar_pool(config)
    except MySQLError as exc:
        app.logger.warning(
            "No fue posible inicializar el pool MySQL al arranque (se reintentara bajo demanda): %s",
            exc,
        )

    registrar_manejadores_error(app)
    registrar_hooks_seguridad(app)
    registrar_rutas(app)

    return app
