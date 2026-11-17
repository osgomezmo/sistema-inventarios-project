from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from flask import jsonify

from app import create_app

TOKEN = "token-de-prueba"
CABECERAS = {"Authorization": f"Bearer {TOKEN}"}
IDENTIFICADOR = "6f1c2a9e-1b7d-4c55-9a51-3f0e8d2b7c10"


@pytest.fixture
def app():
    return create_app({"TESTING": True, "SERVICE_TOKEN": TOKEN})


def consultar(app, datos):
    app.add_url_rule("/prueba-json", view_func=lambda: jsonify(datos))
    return app.test_client().get("/prueba-json", headers=CABECERAS)


def test_decimales_salen_como_numeros(app):
    respuesta = consultar(app, {"cantidad": Decimal("24.500"), "costo": Decimal("3150.0000")})
    cuerpo = respuesta.get_json()

    assert cuerpo["cantidad"] == 24.5
    assert cuerpo["costo"] == 3150.0
    assert isinstance(cuerpo["cantidad"], float)
    assert isinstance(cuerpo["costo"], float)
    assert '"24.500"' not in respuesta.get_data(as_text=True)


def test_datetime_sin_zona_se_interpreta_como_utc(app):
    respuesta = consultar(app, {"fecha": datetime(2026, 10, 20, 14, 32, 5)})
    assert respuesta.get_json()["fecha"] == "2026-10-20T14:32:05Z"


def test_datetime_con_zona_se_convierte_a_utc(app):
    bogota = datetime(2026, 10, 20, 21, 32, 5, tzinfo=ZoneInfo("America/Bogota"))
    respuesta = consultar(app, {"fecha": bogota})
    assert respuesta.get_json()["fecha"] == "2026-10-21T02:32:05Z"


def test_datetime_descarta_los_microsegundos(app):
    respuesta = consultar(app, {"fecha": datetime(2026, 10, 20, 14, 32, 5, 987654)})
    assert respuesta.get_json()["fecha"] == "2026-10-20T14:32:05Z"


def test_date_sale_en_iso(app):
    respuesta = consultar(app, {"dia": date(2026, 10, 20)})
    assert respuesta.get_json()["dia"] == "2026-10-20"


def test_texto_con_tilde_y_enie_sale_sin_escapar(app):
    respuesta = consultar(app, {"nombre": "Categoría de año"})
    assert "Categoría de año" in respuesta.get_data(as_text=True)


def test_el_orden_de_las_claves_se_conserva(app):
    respuesta = consultar(app, {"z": 1, "a": 2})
    assert respuesta.get_data(as_text=True).index('"z"') < respuesta.get_data(as_text=True).index('"a"')


def test_otros_tipos_conocidos_usan_el_proveedor_base(app):
    respuesta = consultar(app, {"id": UUID(IDENTIFICADOR)})
    assert respuesta.get_json()["id"] == IDENTIFICADOR


def test_tipo_no_serializable_responde_500_en_json(app):
    respuesta = consultar(app, {"valor": object()})
    assert respuesta.status_code == 500
    assert respuesta.get_json()["error"]["codigo"] == "ERROR_INTERNO"
