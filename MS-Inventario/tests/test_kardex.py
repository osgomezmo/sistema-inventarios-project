"""Pruebas de GET /kardex (D45) contra el MySQL de desarrollo.

Las bodegas usan el prefijo "ZZT-" y los SKU "ZZTEST-"; un fixture borra al
terminar solo esas filas. Si MySQL no está disponible, las pruebas se saltan.
"""

from datetime import datetime
from decimal import Decimal as D

import pytest

from app import create_app
from app.config import cargar_configuracion
from app.db import abrir_conexion, transaccion
from app.errors import ApiError
from app.servicios.movimientos import aplicar_movimiento

TOKEN = "token-de-prueba"
CABECERAS = {"Authorization": f"Bearer {TOKEN}"}
SKU = "ZZTEST-K"
CONFIG = cargar_configuracion()


def borrar_datos_de_prueba():
    with transaccion(CONFIG) as cur:
        cur.execute("DELETE FROM movimientos WHERE sku LIKE %s", ("ZZTEST-%",))
        cur.execute("DELETE FROM traslados WHERE sku LIKE %s", ("ZZTEST-%",))
        cur.execute("DELETE FROM saldos WHERE sku LIKE %s", ("ZZTEST-%",))
        cur.execute("DELETE FROM bodegas WHERE codigo LIKE %s", ("ZZT-%",))


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


@pytest.fixture
def bodega():
    with transaccion(CONFIG) as cur:
        cur.execute("INSERT INTO bodegas (codigo, nombre, direccion) VALUES (%s, %s, %s)",
                    ("ZZT-K1", "Bodega kardex", "Calle 1"))
        return cur.lastrowid


def movimiento(id_bodega, fecha, tipo, cantidad, saldo, costo="10.0000"):
    """Fila de kardex con fecha controlada (solo en las pruebas)."""
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO movimientos (sku, id_bodega, tipo, cantidad, costo_unitario,"
            " saldo_resultante, costo_promedio, valor_resultante, id_usuario, fecha)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (SKU, id_bodega, tipo, D(cantidad), D(costo), D(saldo), D(costo),
             D(saldo) * D(costo), 7, fecha),
        )
        return cur.lastrowid


def kardex(cliente, **params):
    return cliente.get("/kardex", headers=CABECERAS, query_string=params)


def verificar_error(respuesta, status, codigo):
    assert respuesta.status_code == status, respuesta.get_json()
    error = respuesta.get_json()["error"]
    assert set(error) == {"codigo", "mensaje", "detalles"}
    assert error["codigo"] == codigo
    return error


def test_saldos_con_movimientos_antes_dentro_y_despues(cliente, bodega):
    movimiento(bodega, datetime(2026, 10, 1, 12), "ENTRADA_COMPRA", "10", "10")
    movimiento(bodega, datetime(2026, 10, 31, 12), "SALIDA", "2", "8")
    dentro_1 = movimiento(bodega, datetime(2026, 11, 2, 12), "SALIDA", "3", "5")
    dentro_2 = movimiento(bodega, datetime(2026, 11, 5, 12), "ENTRADA_COMPRA", "4", "9")
    movimiento(bodega, datetime(2026, 11, 20, 12), "SALIDA", "9", "0")

    respuesta = kardex(cliente, sku=SKU, id_bodega=bodega, desde="2026-11-01", hasta="2026-11-10")
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert set(cuerpo) == {"sku", "id_bodega", "desde", "hasta", "saldo_inicial",
                           "movimientos", "saldo_final"}
    assert (cuerpo["desde"], cuerpo["hasta"]) == ("2026-11-01", "2026-11-10")
    assert cuerpo["saldo_inicial"] == {"cantidad": 8, "valor": 80}
    assert [m["id_movimiento"] for m in cuerpo["movimientos"]] == [dentro_1, dentro_2]
    assert cuerpo["saldo_final"] == {"cantidad": 9, "valor": 90}
    assert "id_traslado" not in cuerpo["movimientos"][0]


def test_rango_sin_movimientos(cliente, bodega):
    movimiento(bodega, datetime(2026, 10, 1, 12), "ENTRADA_COMPRA", "6", "6")
    cuerpo = kardex(cliente, sku=SKU, id_bodega=bodega, desde="2026-11-01",
                    hasta="2026-11-10").get_json()
    assert cuerpo["movimientos"] == []
    assert cuerpo["saldo_inicial"] == cuerpo["saldo_final"] == {"cantidad": 6, "valor": 60}


def test_orden_cronologico_con_desempate_por_id(cliente, bodega):
    misma_fecha = datetime(2026, 11, 3, 8)
    ids = [movimiento(bodega, misma_fecha, "ENTRADA_COMPRA", "1", str(i + 1)) for i in range(3)]
    tarde = movimiento(bodega, datetime(2026, 11, 4, 8), "SALIDA", "1", "2")
    cuerpo = kardex(cliente, sku=SKU, id_bodega=bodega, desde="2026-11-01",
                    hasta="2026-11-30").get_json()
    assert [m["id_movimiento"] for m in cuerpo["movimientos"]] == ids + [tarde]


def test_sin_movimientos_da_ceros(cliente, bodega):
    for sku, id_bodega in ((SKU, bodega), ("ZZTEST-NADA", bodega), (SKU, 999_999_999)):
        cuerpo = kardex(cliente, sku=sku, id_bodega=id_bodega, desde="2026-11-01",
                        hasta="2026-11-30").get_json()
        assert cuerpo["saldo_inicial"] == cuerpo["saldo_final"] == {"cantidad": 0, "valor": 0}
        assert cuerpo["movimientos"] == []


def test_parametros_faltantes_dan_422_juntos(cliente):
    error = verificar_error(kardex(cliente), 422, "VALIDACION")
    assert set(error["detalles"]) == {"sku", "id_bodega", "desde", "hasta"}


def test_desde_posterior_a_hasta(cliente, bodega):
    error = verificar_error(
        kardex(cliente, sku=SKU, id_bodega=bodega, desde="2026-11-10", hasta="2026-11-01"),
        422, "VALIDACION")
    assert list(error["detalles"]) == ["desde"]


def test_sin_token(cliente):
    verificar_error(cliente.get("/kardex"), 401, "NO_AUTENTICADO")


def test_kardex_de_una_secuencia_real_es_coherente(cliente, bodega):
    pasos = [("ENTRADA_COMPRA", "10", "50"), ("SALIDA", "3", None),
             ("ENTRADA_COMPRA", "5", "62.5"), ("AJUSTE_NEGATIVO", "2", None)]
    for tipo, cantidad, costo in pasos:
        with transaccion(CONFIG) as cur:
            aplicar_movimiento(cur, sku=SKU, id_bodega=bodega, tipo=tipo, cantidad=D(cantidad),
                               id_usuario=7, unidad_medida="KILO", stock_minimo=D("0"),
                               costo_unitario=None if costo is None else D(costo), motivo="Prueba")
    cuerpo = kardex(cliente, sku=SKU, id_bodega=bodega, desde="2026-01-01",
                    hasta="2100-01-01").get_json()
    filas = cuerpo["movimientos"]
    assert [m["tipo"] for m in filas] == [p[0] for p in pasos]
    previo = D("0")
    for fila in filas:
        cantidad, saldo = D(str(fila["cantidad"])), D(str(fila["saldo_resultante"]))
        signo = 1 if fila["tipo"] == "ENTRADA_COMPRA" else -1
        assert saldo == previo + signo * cantidad
        previo = saldo
    assert cuerpo["saldo_final"]["cantidad"] == 10
