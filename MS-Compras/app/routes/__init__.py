"""Registro de blueprints HTTP de ms-compras."""

from flask import Flask

from app.routes.devoluciones import devoluciones_bp
from app.routes.health import health_bp
from app.routes.ordenes import ordenes_bp


def registrar_rutas(app: Flask) -> None:
    """Registra todos los blueprints de rutas en la instancia Flask."""
    app.register_blueprint(health_bp)
    app.register_blueprint(ordenes_bp)
    app.register_blueprint(devoluciones_bp)
