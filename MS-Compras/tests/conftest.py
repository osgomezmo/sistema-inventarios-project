"""Fixtures compartidas para las pruebas unitarias de ms-compras."""

from pathlib import Path
import sys

import pytest

RAIZ_SERVICIO = Path(__file__).resolve().parent.parent
if str(RAIZ_SERVICIO) not in sys.path:
    sys.path.insert(0, str(RAIZ_SERVICIO))

from app import crear_app
import app.db as modulo_db

SERVICE_TOKEN_PRUEBA = "token-secreto-pruebas-compras"


@pytest.fixture()
def app(monkeypatch):
    """Instancia de Flask configurada de forma aislada sin pool real."""
    monkeypatch.setattr("app.inicializar_pool", lambda _cfg: None)
    monkeypatch.setattr(modulo_db, "_pool", None)

    instancia = crear_app(
        {
            "service_token": SERVICE_TOKEN_PRUEBA,
            "proveedores_url": "http://proveedores.local:3000",
            "proveedores_timeout_seconds": 1.5,
            "rabbitmq_url": "amqp://guest:guest@rabbitmq.local:5672/",
            "rabbitmq_exchange": "inventario.eventos",
        }
    )
    instancia.config["TESTING"] = True
    return instancia


@pytest.fixture()
def client(app):
    """Cliente HTTP de pruebas de Flask."""
    return app.test_client()


def auth_headers(rol: str = "compras", user_id: str = "7", corr: str = "corr-test-1") -> dict[str, str]:
    """Construye encabezados estandar de gateway para pruebas de rutas."""
    return {
        "Authorization": f"Bearer {SERVICE_TOKEN_PRUEBA}",
        "X-User-Id": str(user_id),
        "X-User-Role": rol,
        "X-Correlation-Id": corr,
    }
