"""Configuración común de las pruebas."""

import pytest


@pytest.fixture(autouse=True)
def sin_publicacion_de_eventos(monkeypatch):
    """Las pruebas no publican en el RabbitMQ real: RABBITMQ_URL vacía desactiva
    la publicación (D48). load_dotenv no pisa una variable ya definida. La prueba
    de integración con el broker lee la URL real del .env por su cuenta."""
    monkeypatch.setenv("RABBITMQ_URL", "")
