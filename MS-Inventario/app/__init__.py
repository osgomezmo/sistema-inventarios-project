from flask import Flask

from app.auth import registrar_autenticacion
from app.config import cargar_configuracion
from app.errors import registrar_manejadores_de_error
from app.json_provider import ProveedorJson
from app.routes.bodegas import bodegas_bp
from app.routes.devoluciones import devoluciones_bp
from app.routes.health import health_bp
from app.routes.kardex import kardex_bp
from app.routes.movimientos import movimientos_bp
from app.routes.stock import stock_bp
from app.routes.traslados import traslados_bp


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
    app.register_blueprint(bodegas_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(movimientos_bp)
    app.register_blueprint(kardex_bp)
    app.register_blueprint(traslados_bp)
    app.register_blueprint(devoluciones_bp)

    return app
