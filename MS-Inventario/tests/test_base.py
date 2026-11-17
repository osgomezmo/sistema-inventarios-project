import pytest
from flask import abort

from app import create_app
from app.errors import ApiError

TOKEN = "token-de-prueba"
CABECERAS = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def app():
    return create_app({"TESTING": True, "SERVICE_TOKEN": TOKEN})


@pytest.fixture
def cliente(app):
    return app.test_client()


def verificar_error(respuesta, status, codigo):
    assert respuesta.status_code == status
    assert respuesta.is_json
    error = respuesta.get_json()["error"]
    assert set(error) == {"codigo", "mensaje", "detalles"}
    assert error["codigo"] == codigo


def test_health_sin_token(cliente):
    respuesta = cliente.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"estado": "ok"}


def test_ruta_sin_token_responde_401(cliente):
    verificar_error(cliente.get("/stock"), 401, "NO_AUTENTICADO")


def test_token_incorrecto_responde_401(cliente):
    respuesta = cliente.get("/stock", headers={"Authorization": "Bearer otro-token"})
    verificar_error(respuesta, 401, "NO_AUTENTICADO")


def test_esquema_distinto_de_bearer_responde_401(cliente):
    respuesta = cliente.get("/stock", headers={"Authorization": f"Basic {TOKEN}"})
    verificar_error(respuesta, 401, "NO_AUTENTICADO")


def test_ruta_inexistente_con_token_responde_404_en_json(cliente):
    verificar_error(cliente.get("/no-existe", headers=CABECERAS), 404, "NO_EXISTE")


def test_metodo_no_permitido_responde_405_en_json(cliente):
    respuesta = cliente.post("/health", headers=CABECERAS)
    verificar_error(respuesta, 405, "METODO_NO_PERMITIDO")
    assert "GET" in respuesta.headers["Allow"]


def test_sin_service_token_el_servicio_no_arranca():
    with pytest.raises(RuntimeError, match="SERVICE_TOKEN"):
        create_app({"SERVICE_TOKEN": ""})


def test_token_de_ejemplo_no_permite_arrancar():
    with pytest.raises(RuntimeError, match="valor de ejemplo"):
        create_app({"SERVICE_TOKEN": "cambia-este-token"})


@pytest.mark.parametrize(
    "status, codigo",
    [
        (400, "PETICION_INVALIDA"),
        (403, "SIN_PERMISO"),
        (409, "CONFLICTO"),
        (422, "VALIDACION"),
        (503, "SERVICIO_NO_DISPONIBLE"),
    ],
)
def test_abort_responde_en_formato_de_error(app, status, codigo):
    app.add_url_rule("/prueba-abort", view_func=lambda: abort(status))
    respuesta = app.test_client().get("/prueba-abort", headers=CABECERAS)
    verificar_error(respuesta, status, codigo)


def test_api_error_conserva_codigo_y_detalles(app):
    detalles = {"cantidad": ["Supera el saldo disponible."]}

    def fallar():
        raise ApiError("STOCK_INSUFICIENTE", "No hay saldo suficiente.", 409, detalles)

    app.add_url_rule("/prueba-api-error", view_func=fallar)
    respuesta = app.test_client().get("/prueba-api-error", headers=CABECERAS)
    verificar_error(respuesta, 409, "STOCK_INSUFICIENTE")
    assert respuesta.get_json()["error"]["detalles"] == detalles


def test_error_inesperado_responde_500_sin_revelar_el_detalle(app):
    def fallar():
        raise ValueError("detalle interno")

    app.add_url_rule("/prueba-error-interno", view_func=fallar)
    respuesta = app.test_client().get("/prueba-error-interno", headers=CABECERAS)
    verificar_error(respuesta, 500, "ERROR_INTERNO")
    assert "detalle interno" not in respuesta.get_data(as_text=True)
