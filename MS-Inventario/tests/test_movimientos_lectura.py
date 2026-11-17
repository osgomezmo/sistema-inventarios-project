"""Pruebas de GET /movimientos y GET /movimientos/{id} contra el MySQL de desarrollo.

Las bodegas usan el prefijo de código PREFIJO_BODEGA y los movimientos el
prefijo de SKU PREFIJO_SKU. Los movimientos se insertan con SQL directo y con
fecha controlada (solo en las pruebas). Un fixture borra al terminar solo esas
filas, en este orden: movimientos, traslados, saldos y bodegas. Si MySQL no
está disponible, las pruebas se saltan.
"""

import json
from datetime import datetime
from decimal import Decimal as D

import pytest

from app import create_app
from app.config import cargar_configuracion
from app.db import abrir_conexion, transaccion
from app.errors import ApiError

PREFIJO_BODEGA = "ZZT-"
PREFIJO_SKU = "ZZTEST-"
TOKEN = "token-de-prueba"
CABECERAS = {"Authorization": f"Bearer {TOKEN}"}
CAMPOS = {
    "id_movimiento", "sku", "id_bodega", "tipo", "cantidad", "costo_unitario",
    "saldo_resultante", "costo_promedio", "valor_resultante", "motivo",
    "documento_referencia", "id_usuario", "fecha",
}
NUMERICOS = ("cantidad", "costo_unitario", "saldo_resultante", "costo_promedio", "valor_resultante")
TIPOS = (
    "ENTRADA_COMPRA", "AJUSTE_POSITIVO", "TRASLADO_ENTRADA", "DEVOLUCION_CLIENTE",
    "SALIDA", "AJUSTE_NEGATIVO", "TRASLADO_SALIDA", "DEVOLUCION_PROVEEDOR",
)
CONFIG = cargar_configuracion()

# Bordes del día en Bogotá (UTC-5)
ULTIMO_SEGUNDO_DEL_9 = datetime(2026, 11, 10, 4, 59, 59)   # 2026-11-09 23:59:59 en Bogotá
PRIMER_SEGUNDO_DEL_10 = datetime(2026, 11, 10, 5, 0, 0)    # 2026-11-10 00:00:00 en Bogotá


def patron_like(prefijo):
    # En LIKE, "_" y "%" son comodines: se escapan para filtrar solo el prefijo exacto.
    return prefijo.replace("\\", "\\\\").replace("_", "\\_").replace("%", "\\%") + "%"


def borrar_datos_de_prueba():
    sku, bodega = patron_like(PREFIJO_SKU), patron_like(PREFIJO_BODEGA)
    with transaccion(CONFIG) as cur:
        cur.execute("DELETE FROM movimientos WHERE sku LIKE %s", (sku,))
        cur.execute("DELETE FROM traslados WHERE sku LIKE %s", (sku,))
        cur.execute("DELETE FROM saldos WHERE sku LIKE %s", (sku,))
        cur.execute("DELETE FROM bodegas WHERE codigo LIKE %s", (bodega,))


@pytest.fixture(scope="module", autouse=True)
def mysql_disponible():
    try:
        abrir_conexion(CONFIG).close()
    except ApiError:
        pytest.skip("MySQL de desarrollo no disponible en 127.0.0.1:33062")


@pytest.fixture(autouse=True)
def limpiar():
    borrar_datos_de_prueba()
    yield
    borrar_datos_de_prueba()


@pytest.fixture
def cliente():
    return create_app({"TESTING": True, "SERVICE_TOKEN": TOKEN}).test_client()


def crear_bodega(codigo):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO bodegas (codigo, nombre, direccion) VALUES (%s, %s, %s)",
            (PREFIJO_BODEGA + codigo, f"Bodega {codigo}", "Calle 1"),
        )
        return cur.lastrowid


def crear_movimiento(id_bodega, fecha, *, sku="A1", tipo="ENTRADA_COMPRA", cantidad="2.500",
                     costo="3150.1234", motivo=None, documento=None):
    """Inserta un movimiento con fecha controlada (solo para las pruebas)."""
    saldo = D(cantidad)
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO movimientos (sku, id_bodega, tipo, cantidad, costo_unitario,"
            " saldo_resultante, costo_promedio, valor_resultante, motivo,"
            " documento_referencia, id_usuario, fecha)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (PREFIJO_SKU + sku, id_bodega, tipo, D(cantidad), D(costo), saldo, D(costo),
             (saldo * D(costo)).quantize(D("0.01")), motivo, documento, 7, fecha),
        )
        return cur.lastrowid


@pytest.fixture
def bodegas():
    return crear_bodega("B1"), crear_bodega("B2")


@pytest.fixture
def bordes(bodegas):
    """Dos movimientos a un segundo de distancia, a ambos lados de la medianoche en Bogotá."""
    b1, _ = bodegas
    return {
        "dia9": crear_movimiento(b1, ULTIMO_SEGUNDO_DEL_9, sku="FECHA"),
        "dia10": crear_movimiento(b1, PRIMER_SEGUNDO_DEL_10, sku="FECHA"),
    }


def get(cliente, ruta, **params):
    return cliente.get(ruta, headers=CABECERAS, query_string=params)


def listar(cliente, **params):
    respuesta = get(cliente, "/movimientos", **params)
    assert respuesta.status_code == 200, respuesta.get_json()
    return respuesta.get_json()


def ids(cuerpo):
    return [m["id_movimiento"] for m in cuerpo["data"]]


def verificar_error(respuesta, status, codigo):
    assert respuesta.status_code == status, respuesta.get_json()
    error = respuesta.get_json()["error"]
    assert set(error) == {"codigo", "mensaje", "detalles"}
    assert error["codigo"] == codigo
    return error


# --- Listado ----------------------------------------------------------------


def test_listado_con_campos_exactos(cliente, bodegas):
    b1, _ = bodegas
    id_mov = crear_movimiento(b1, datetime(2026, 11, 1, 12, 0, 0))
    respuesta = get(cliente, "/movimientos", sku="ZZTEST-A1")
    crudo = json.loads(respuesta.get_data(as_text=True))
    assert crudo["meta"] == {"page": 1, "per_page": 20, "total": 1}
    movimiento = crudo["data"][0]
    assert set(movimiento) == CAMPOS
    assert movimiento["id_movimiento"] == id_mov
    for campo in NUMERICOS:
        assert isinstance(movimiento[campo], (int, float)) and not isinstance(movimiento[campo], bool)
    assert movimiento["cantidad"] == 2.5
    assert movimiento["costo_unitario"] == 3150.1234
    assert movimiento["valor_resultante"] == 7875.31
    assert movimiento["motivo"] is None and movimiento["documento_referencia"] is None
    assert movimiento["fecha"] == "2026-11-01T12:00:00Z"
    assert movimiento["id_usuario"] == 7 and movimiento["id_bodega"] == b1


def test_orden_mas_reciente_primero_con_desempate_por_id(cliente, bodegas):
    b1, _ = bodegas
    viejo = crear_movimiento(b1, datetime(2026, 1, 1, 0, 0, 0))
    mismo_a = crear_movimiento(b1, datetime(2026, 6, 1, 0, 0, 0))
    mismo_b = crear_movimiento(b1, datetime(2026, 6, 1, 0, 0, 0))
    nuevo = crear_movimiento(b1, datetime(2026, 9, 1, 0, 0, 0))
    assert ids(listar(cliente, sku="ZZTEST-A1")) == [nuevo, mismo_b, mismo_a, viejo]


@pytest.mark.parametrize("sku", ["ZZTEST-A1", "zztest-a1", "  ZZTEST-A1  "])
def test_filtro_sku(cliente, bodegas, sku):
    b1, _ = bodegas
    propio = crear_movimiento(b1, datetime(2026, 1, 1))
    crear_movimiento(b1, datetime(2026, 1, 1), sku="OTRO")
    assert ids(listar(cliente, sku=sku)) == [propio]


def test_filtro_id_bodega(cliente, bodegas):
    b1, b2 = bodegas
    crear_movimiento(b1, datetime(2026, 1, 1))
    en_b2 = crear_movimiento(b2, datetime(2026, 1, 1))
    assert ids(listar(cliente, sku="ZZTEST-A1", id_bodega=b2)) == [en_b2]


def test_id_bodega_inexistente_da_lista_vacia(cliente, bodegas):
    crear_movimiento(bodegas[0], datetime(2026, 1, 1))
    assert listar(cliente, id_bodega=999_999_999) == {
        "data": [], "meta": {"page": 1, "per_page": 20, "total": 0}}


@pytest.mark.parametrize("tipo", TIPOS)
def test_filtro_tipo(cliente, bodegas, tipo):
    b1, _ = bodegas
    por_tipo = {t: crear_movimiento(b1, datetime(2026, 1, 1), tipo=t) for t in TIPOS}
    cuerpo = listar(cliente, sku="ZZTEST-A1", tipo=tipo)
    assert ids(cuerpo) == [por_tipo[tipo]]
    assert cuerpo["data"][0]["tipo"] == tipo


def test_filtros_combinados(cliente, bodegas):
    b1, b2 = bodegas
    objetivo = crear_movimiento(b2, datetime(2026, 3, 1), tipo="SALIDA")
    crear_movimiento(b2, datetime(2026, 3, 1), tipo="ENTRADA_COMPRA")
    crear_movimiento(b1, datetime(2026, 3, 1), tipo="SALIDA")
    crear_movimiento(b2, datetime(2025, 3, 1), tipo="SALIDA")
    cuerpo = listar(cliente, sku="zztest-a1", id_bodega=b2, tipo="SALIDA", desde="2026-01-01")
    assert ids(cuerpo) == [objetivo]


def test_motivo_y_documento_cuando_existen(cliente, bodegas):
    crear_movimiento(bodegas[0], datetime(2026, 1, 1), tipo="AJUSTE_POSITIVO",
                     motivo="Conteo físico", documento="OC-15")
    movimiento = listar(cliente, sku="ZZTEST-A1")["data"][0]
    assert (movimiento["motivo"], movimiento["documento_referencia"]) == ("Conteo físico", "OC-15")


# --- Bordes de fecha ----------------------------------------------------------------


@pytest.mark.parametrize(
    "params, esperados",
    [
        ({"desde": "2026-11-10"}, ["dia10"]),
        ({"hasta": "2026-11-09"}, ["dia9"]),
        ({"hasta": "2026-11-10"}, ["dia10", "dia9"]),
        ({"desde": "2026-11-09", "hasta": "2026-11-09"}, ["dia9"]),
        ({"desde": "2026-11-10", "hasta": "2026-11-10"}, ["dia10"]),
        ({"desde": "2026-11-10T05:00:00Z"}, ["dia10"]),
        ({"hasta": "2026-11-10T05:00:00Z"}, ["dia10", "dia9"]),
        ({"hasta": "2026-11-10T04:59:59Z"}, ["dia9"]),
        ({"desde": "2026-11-10T00:00:00-05:00"}, ["dia10"]),
        ({"hasta": "2026-11-09T23:59:59-05:00"}, ["dia9"]),
        ({"desde": "2026-11-10T05:00:00"}, ["dia10"]),  # sin zona: UTC
        ({"hasta": "2026-11-10T04:59:59"}, ["dia9"]),
        ({"desde": "2026-11-10T04:59:59Z", "hasta": "2026-11-10T04:59:59Z"}, ["dia9"]),
        ({"desde": "2026-11-11"}, []),
        ({"hasta": "2026-11-08"}, []),
    ],
)
def test_bordes_de_fecha(cliente, bordes, params, esperados):
    cuerpo = listar(cliente, sku="ZZTEST-FECHA", **params)
    assert ids(cuerpo) == [bordes[nombre] for nombre in esperados]


@pytest.mark.parametrize(
    "params",
    [
        {"desde": "2026-11-10", "hasta": "2026-11-09"},
        {"desde": "2026-11-10T05:00:01Z", "hasta": "2026-11-10T05:00:00Z"},
        {"desde": "2026-11-11T05:00:00Z", "hasta": "2026-11-10"},
    ],
)
def test_desde_posterior_a_hasta_da_422(cliente, params):
    error = verificar_error(get(cliente, "/movimientos", **params), 422, "VALIDACION")
    assert list(error["detalles"]) == ["desde"]


@pytest.mark.parametrize(
    "params, campo",
    [
        ({"desde": "abc"}, "desde"),
        ({"hasta": "2026-02-30"}, "hasta"),
        ({"desde": "10/11/2026"}, "desde"),
        ({"hasta": "1999-12-31"}, "hasta"),
        ({"tipo": "salida"}, "tipo"),
        ({"tipo": "REGALO"}, "tipo"),
        ({"per_page": 101}, "per_page"),
        ({"sku": "X" * 51}, "sku"),
        ({"id_bodega": "abc"}, "id_bodega"),
    ],
)
def test_filtros_invalidos_dan_422(cliente, params, campo):
    error = verificar_error(get(cliente, "/movimientos", **params), 422, "VALIDACION")
    assert list(error["detalles"]) == [campo]


def test_varios_errores_juntos(cliente):
    error = verificar_error(
        get(cliente, "/movimientos", desde="abc", hasta="2026-13-01", tipo="x", per_page=101,
            sku="X" * 51),
        422, "VALIDACION")
    assert set(error["detalles"]) == {"desde", "hasta", "tipo", "per_page", "sku"}


# --- Paginación ---------------------------------------------------------------------------


def test_paginacion_coherente(cliente, bodegas):
    b1, _ = bodegas
    for dia in (1, 2, 2, 3, 4):
        crear_movimiento(b1, datetime(2026, 5, dia))
    completas = listar(cliente, sku="ZZTEST-A1", per_page=100)
    paginadas, page = [], 1
    while True:
        cuerpo = listar(cliente, sku="ZZTEST-A1", per_page=2, page=page)
        assert cuerpo["meta"]["page"] == page and cuerpo["meta"]["per_page"] == 2
        paginadas.extend(ids(cuerpo))
        if page * 2 >= cuerpo["meta"]["total"]:
            break
        page += 1
    assert len(paginadas) == len(set(paginadas)) == completas["meta"]["total"] == 5
    assert paginadas == ids(completas)


def test_pagina_mas_alla_del_final(cliente, bodegas):
    crear_movimiento(bodegas[0], datetime(2026, 1, 1))
    cuerpo = listar(cliente, sku="ZZTEST-A1", per_page=2, page=5)
    assert cuerpo["data"] == [] and cuerpo["meta"]["total"] == 1


# --- Consulta por id ----------------------------------------------------------------------


def test_obtener_por_id(cliente, bodegas):
    id_mov = crear_movimiento(bodegas[0], datetime(2026, 11, 1, 12, 0, 0), documento="OC-1")
    respuesta = get(cliente, f"/movimientos/{id_mov}")
    assert respuesta.status_code == 200
    movimiento = respuesta.get_json()
    assert set(movimiento) == CAMPOS
    assert movimiento["id_movimiento"] == id_mov
    assert movimiento["documento_referencia"] == "OC-1"
    assert movimiento["fecha"] == "2026-11-01T12:00:00Z"
    assert movimiento == listar(cliente, sku="ZZTEST-A1")["data"][0]


def test_obtener_inexistente_da_404(cliente):
    error = verificar_error(get(cliente, "/movimientos/999999999"), 404, "NO_EXISTE")
    assert error["mensaje"] == "El movimiento no existe."


@pytest.mark.parametrize("ruta", ["/movimientos/abc", "/movimientos/-1", "/movimientos/1.5"])
def test_id_no_entero_da_404(cliente, ruta):
    verificar_error(get(cliente, ruta), 404, "NO_EXISTE")


# --- Autenticación y métodos ----------------------------------------------------------------


@pytest.mark.parametrize("ruta", ["/movimientos", "/movimientos/1"])
def test_sin_token_da_401(cliente, ruta):
    verificar_error(cliente.get(ruta), 401, "NO_AUTENTICADO")


def test_post_sobre_un_movimiento_no_esta_permitido(cliente):
    # POST /movimientos sí existe (D44); sobre un movimiento concreto no: el kardex es inmutable.
    respuesta = cliente.post("/movimientos/1", headers=CABECERAS, json={})
    verificar_error(respuesta, 405, "METODO_NO_PERMITIDO")
