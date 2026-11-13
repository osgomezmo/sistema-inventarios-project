from decimal import Decimal

import pytest
from flask import Flask

from app.errors import ApiError
from app.paginacion import leer_paginacion, respuesta_paginada
from app.validacion import (
    Errores,
    decimal_opcional,
    entero_opcional,
    leer_json,
    lista_separada_por_comas,
    opcion,
    texto_obligatorio,
    texto_opcional,
)

app = Flask(__name__)


def paginacion(query):
    with app.test_request_context(f"/?{query}"):
        return leer_paginacion()


def error_de_paginacion(query):
    with pytest.raises(ApiError) as info:
        paginacion(query)
    assert (info.value.status, info.value.codigo) == (422, "VALIDACION")
    return info.value.detalles


# --- Paginación -------------------------------------------------------------


def test_paginacion_por_defecto():
    assert paginacion("") == (1, 20, 0)


@pytest.mark.parametrize(
    "query, esperado",
    [
        ("page=1&per_page=1", (1, 1, 0)),
        ("page=3&per_page=100", (3, 100, 200)),
        ("page=2", (2, 20, 20)),
        ("per_page=5", (1, 5, 0)),
        ("page=&per_page=", (1, 20, 0)),
    ],
)
def test_paginacion_valida(query, esperado):
    assert paginacion(query) == esperado


@pytest.mark.parametrize(
    "query, campo",
    [
        ("page=0", "page"),
        ("page=-1", "page"),
        ("page=uno", "page"),
        ("page=1.5", "page"),
        ("per_page=0", "per_page"),
        ("per_page=101", "per_page"),
        ("per_page=diez", "per_page"),
    ],
)
def test_paginacion_invalida_responde_422(query, campo):
    detalles = error_de_paginacion(query)
    assert list(detalles) == [campo]
    assert len(detalles[campo]) == 1


def test_paginacion_reporta_los_dos_campos_a_la_vez():
    detalles = error_de_paginacion("page=0&per_page=500")
    assert set(detalles) == {"page", "per_page"}


def test_paginacion_acumula_en_errores_externos():
    errores = Errores()
    with app.test_request_context("/?per_page=101"):
        leer_paginacion(errores)
    assert set(errores.detalles) == {"per_page"}


def test_respuesta_paginada():
    assert respuesta_paginada([{"id": 1}], 2, 10, 11) == {
        "data": [{"id": 1}],
        "meta": {"page": 2, "per_page": 10, "total": 11},
    }


# --- Validación -------------------------------------------------------------


def test_errores_vacios_no_lanzan():
    errores = Errores()
    assert not errores
    errores.lanzar_si_hay()


def test_errores_se_acumulan_por_campo():
    errores = Errores()
    datos = {"nombre": "", "descripcion": 5, "estado": "BORRADO", "id": "x"}

    texto_obligatorio(errores, datos, "nombre", 100)
    texto_opcional(errores, datos, "descripcion", 255)
    opcion(errores, datos, "estado", ("ACTIVO", "INACTIVO"))
    entero_opcional(errores, datos, "id")
    errores.agregar("nombre", "Otro problema.")

    with pytest.raises(ApiError) as info:
        errores.lanzar_si_hay()
    error = info.value
    assert (error.status, error.codigo, error.mensaje) == (
        422, "VALIDACION", "Revisa los campos enviados.")
    assert set(error.detalles) == {"nombre", "descripcion", "estado", "id"}
    assert error.detalles["nombre"] == ["Es obligatorio.", "Otro problema."]


@pytest.mark.parametrize(
    "valor, esperado, hay_error",
    [
        ("  Lácteos  ", "Lácteos", False),
        ("x" * 100, "x" * 100, False),
        ("x" * 101, None, True),
        ("   ", None, True),
        (None, None, True),
        (7, None, True),
    ],
)
def test_texto_obligatorio(valor, esperado, hay_error):
    errores = Errores()
    assert texto_obligatorio(errores, {"nombre": valor}, "nombre", 100) == esperado
    assert bool(errores) is hay_error


@pytest.mark.parametrize(
    "valor, esperado, hay_error",
    [
        (None, None, False),
        ("", None, False),
        ("  ", None, False),
        (" Leches ", "Leches", False),
        ("x" * 11, None, True),
        (["a"], None, True),
    ],
)
def test_texto_opcional(valor, esperado, hay_error):
    errores = Errores()
    assert texto_opcional(errores, {"campo": valor}, "campo", 10) == esperado
    assert bool(errores) is hay_error


@pytest.mark.parametrize(
    "valor, esperado, hay_error",
    [
        (None, None, False),
        ("", None, False),
        (5, 5, False),
        ("5", 5, False),
        (" 12 ", 12, False),
        (0, None, True),
        (5.0, None, True),
        ("5.0", None, True),
        (True, None, True),
        ("abc", None, True),
    ],
)
def test_entero_opcional_con_minimo(valor, esperado, hay_error):
    errores = Errores()
    assert entero_opcional(errores, {"id": valor}, "id", minimo=1) == esperado
    assert bool(errores) is hay_error


@pytest.mark.parametrize(
    "valor, esperado, hay_error",
    [
        ("ACTIVO", "ACTIVO", False),
        (None, None, False),
        ("activo", None, True),
        ("BORRADO", None, True),
    ],
)
def test_opcion(valor, esperado, hay_error):
    errores = Errores()
    assert opcion(errores, {"estado": valor}, "estado", ("ACTIVO", "INACTIVO")) == esperado
    assert bool(errores) is hay_error


def test_opcion_obligatoria_sin_valor():
    errores = Errores()
    opcion(errores, {}, "estado", ("ACTIVO",), obligatorio=True)
    assert errores.detalles == {"estado": ["Es obligatorio."]}


# --- Cuerpo JSON ------------------------------------------------------------


def test_leer_json_devuelve_el_objeto():
    with app.test_request_context("/", method="POST", json={"nombre": "Lácteos"}):
        assert leer_json() == {"nombre": "Lácteos"}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"data": "nombre=Lácteos", "content_type": "application/x-www-form-urlencoded"},
        {"data": "{no es json", "content_type": "application/json"},
        {"data": "[1, 2]", "content_type": "application/json"},
        {},
    ],
)
def test_leer_json_invalido_responde_400(kwargs):
    with app.test_request_context("/", method="POST", **kwargs):
        with pytest.raises(ApiError) as info:
            leer_json()
    assert (info.value.status, info.value.codigo) == (400, "PETICION_INVALIDA")


@pytest.mark.parametrize(
    "valor, esperado, hay_error",
    [
        (None, None, False),
        ("", None, False),
        ("0", Decimal("0"), False),
        ("12", Decimal("12"), False),
        (" 12.50 ", Decimal("12.50"), False),
        (3, Decimal("3"), False),
        (2.5, Decimal("2.5"), False),
        ("12.505", None, True),
        ("-1", None, True),
        ("abc", None, True),
        ("nan", None, True),
        ("inf", None, True),
        ("1e3", None, True),
        (float("nan"), None, True),
        (float("inf"), None, True),
        (True, None, True),
    ],
)
def test_decimal_opcional(valor, esperado, hay_error):
    errores = Errores()
    resultado = decimal_opcional(errores, {"precio": valor}, "precio", minimo=0, decimales=2)
    assert resultado == esperado
    assert bool(errores) is hay_error
    if esperado is not None:
        assert isinstance(resultado, Decimal)


@pytest.mark.parametrize(
    "valor, esperado, hay_error",
    [
        (None, None, False),
        ("", [], False),
        (" , ,", [], False),
        ("A", ["A"], False),
        (" A , B,,C ", ["A", "B", "C"], False),
        (",".join(["X"] * 3), ["X"] * 3, False),
        (",".join(["X"] * 4), None, True),
        ("A,BBBBBB", None, True),
        (["A"], None, True),
    ],
)
def test_lista_separada_por_comas(valor, esperado, hay_error):
    errores = Errores()
    resultado = lista_separada_por_comas(errores, {"skus": valor}, "skus", 3, 5)
    assert resultado == esperado
    assert bool(errores) is hay_error
