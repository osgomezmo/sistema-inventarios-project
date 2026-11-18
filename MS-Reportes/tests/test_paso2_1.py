import uuid
import pytest
from flask import Blueprint, g, jsonify

from app import create_app
from app.db import set_transaccion_override, transaccion
from app.errors import ApiError

test_bp = Blueprint("test_routes", __name__)


@test_bp.get("/protegido")
def ruta_protegida():
    return jsonify({
        "ok": True,
        "user_id": g.user_id,
        "user_role": g.user_role,
        "correlation_id": g.correlation_id,
    })


@test_bp.get("/forzar-error")
def ruta_forzar_error():
    raise ApiError("ERROR_DE_PRUEBA", "Este es un fallo inducido", 400, {"campo": "invalido"})


@pytest.fixture
def cliente():
    app = create_app({
        "TESTING": True,
        "SERVICE_TOKEN": "token-test-2026",
    })
    app.register_blueprint(test_bp)
    with app.test_client() as c:
        yield c


def test_health_publico(cliente):
    res = cliente.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["servicio"] == "ms-reportes"


def test_requiere_token_401(cliente):
    # Sin header
    res = cliente.get("/protegido")
    assert res.status_code == 401
    data = res.get_json()
    assert data["error"]["codigo"] == "NO_AUTENTICADO"
    assert "error" in data
    assert "mensaje" in data["error"]

    # Con token invalido
    res = cliente.get("/protegido", headers={"Authorization": "Bearer token-falso"})
    assert res.status_code == 401
    data = res.get_json()
    assert data["error"]["codigo"] == "NO_AUTENTICADO"


def test_token_valido_y_extraccion_headers(cliente):
    correlacion = str(uuid.uuid4())
    headers = {
        "Authorization": "Bearer token-test-2026",
        "X-User-Id": "42",
        "X-User-Role": "admin",
        "X-Correlation-Id": correlacion,
    }
    res = cliente.get("/protegido", headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["user_id"] == "42"
    assert data["user_role"] == "admin"
    assert data["correlation_id"] == correlacion
    assert res.headers.get("X-Correlation-Id") == correlacion


def test_generacion_correlation_id_si_falta(cliente):
    headers = {
        "Authorization": "Bearer token-test-2026",
    }
    res = cliente.get("/protegido", headers=headers)
    assert res.status_code == 200
    resp_corr = res.headers.get("X-Correlation-Id")
    assert resp_corr is not None
    assert len(resp_corr) > 0


def test_formato_estandar_de_error(cliente):
    headers = {"Authorization": "Bearer token-test-2026"}
    res = cliente.get("/forzar-error", headers=headers)
    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data
    assert data["error"]["codigo"] == "ERROR_DE_PRUEBA"
    assert data["error"]["mensaje"] == "Este es un fallo inducido"
    assert data["error"]["detalles"] == {"campo": "invalido"}


def test_error_http_404_estandar(cliente):
    headers = {"Authorization": "Bearer token-test-2026"}
    res = cliente.get("/ruta-que-no-existe", headers=headers)
    assert res.status_code == 404
    data = res.get_json()
    assert data["error"]["codigo"] == "NO_EXISTE"


def test_transaccion_mock_injection():
    # Simula inyeccion de mock de transaccion
    class MockCursor:
        def __init__(self):
            self.ejecutadas = []

        def execute(self, sql, params=None):
            self.ejecutadas.append((sql, params))

    class MockContextManager:
        def __init__(self, config=None):
            self.cursor = MockCursor()
            self.commited = False
            self.rolled_back = False

        def __enter__(self):
            return self.cursor

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                self.commited = True
            else:
                self.rolled_back = True
            return False

        def __call__(self, config=None):
            return self

    mock_tx = MockContextManager()
    set_transaccion_override(mock_tx)

    try:
        with transaccion() as cur:
            cur.execute("SELECT 1")
        assert mock_tx.commited is True
        assert len(mock_tx.cursor.ejecutadas) == 1

        with pytest.raises(ValueError):
            with transaccion() as cur:
                cur.execute("SELECT 2")
                raise ValueError("error en bloque")
        assert mock_tx.rolled_back is True
    finally:
        set_transaccion_override(None)
