from flask import Flask

from app.auth import registrar_autenticacion
from app.config import cargar_configuracion
from app.errors import registrar_manejadores_de_error
from app.json_provider import ProveedorJson
from app.routes.categorias import categorias_bp
from app.routes.health import health_bp


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(cargar_configuracion())
    if config:
        app.config.update(config)

    app.json = ProveedorJson(app)
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    registrar_manejadores_de_error(app)
    registrar_autenticacion(app)
    app.register_blueprint(health_bp)
    app.register_blueprint(categorias_bp)

    return app
