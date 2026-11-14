"""Pruebas de procesar_evento (D49) contra el MySQL de desarrollo.

consultar_producto se reemplaza por un falso. Bodegas con prefijo "ZZT-", SKU
"ZZTEST-" e id_evento propios de cada prueba, que se borran al terminar (solo
esos). Si MySQL no está disponible, las pruebas se saltan.
"""

import json
import uuid
from decimal import Decimal as D

import pytest

import app.servicios.eventos_entrantes as entrantes
from app import create_app
from app.config import cargar_configuracion
from app.db import abrir_conexion, transaccion
from app.errors import ApiError
from app.servicios.eventos_entrantes import EventoInvalido, procesar_evento

CONFIG = cargar_configuracion()
PRODUCTOS = {
    "ZZTEST-EA": {"unidad_medida": "KILO", "stock_minimo": D("1")},
    "ZZTEST-EB": {"unidad_medida": "UNIDAD", "stock_minimo": D("0")},
}
EVENTOS_DE_PRUEBA = []


def borrar_datos_de_prueba():
    with transaccion(CONFIG) as cur:
        cur.execute("DELETE FROM movimientos WHERE sku LIKE %s", ("ZZTEST-%",))
        cur.execute("DELETE FROM traslados WHERE sku LIKE %s", ("ZZTEST-%",))
        cur.execute("DELETE FROM saldos WHERE sku LIKE %s", ("ZZTEST-%",))
        cur.execute("DELETE FROM bodegas WHERE codigo LIKE %s", ("ZZT-%",))
        if EVENTOS_DE_PRUEBA:
            marcadores = ", ".join(["%s"] * len(EVENTOS_DE_PRUEBA))
            cur.execute(f"DELETE FROM eventos_procesados WHERE id_evento IN ({marcadores})",
                        EVENTOS_DE_PRUEBA)


@pytest.fixture(scope="module", autouse=True)
def mysql_disponible():
    try:
        abrir_conexion(CONFIG).close()
    except ApiError:
        pytest.skip("MySQL de desarrollo no disponible en 127.0.0.1:33062")


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    borrar_datos_de_prueba()
    consultas = []

    def falso(sku, id_correlacion=None):
        consultas.append((sku, id_correlacion))
        canonico = sku.upper()
        if canonico not in PRODUCTOS:
            raise ApiError("PRODUCTO_INEXISTENTE", "El producto no existe.", 404)
        return {"sku": canonico, "nombre": "Producto", "estado": "ACTIVO", "id_categoria": 1,
                **PRODUCTOS[canonico]}

    monkeypatch.setattr(entrantes, "consultar_producto", falso)
    app = create_app({"TESTING": True, "SERVICE_TOKEN": "token-de-prueba"})
    with app.app_context():
        yield consultas
    borrar_datos_de_prueba()
    EVENTOS_DE_PRUEBA.clear()


@pytest.fixture
def bodega():
    with transaccion(CONFIG) as cur:
        cur.execute("INSERT INTO bodegas (codigo, nombre, direccion) VALUES (%s, %s, %s)",
                    ("ZZT-EV1", "Bodega eventos", "Calle 1"))
        return cur.lastrowid


def nuevo_id():
    id_evento = str(uuid.uuid4())
    EVENTOS_DE_PRUEBA.append(id_evento)
    return id_evento


def sobre(tipo, datos, id_evento=None, id_correlacion="corr-ev"):
    cuerpo = {"id_evento": id_evento or nuevo_id(), "tipo": tipo, "fecha": "2026-11-14T12:00:00Z",
              "productor": "ms-compras", "id_correlacion": id_correlacion, "datos": datos}
    return json.dumps(cuerpo).encode()


def mercancia(id_bodega, items, **extra):
    return {"id_orden": 15, "id_recepcion": 31, "id_bodega": id_bodega, "id_usuario": 7,
            "items": items, **extra}


def devolucion(id_bodega, items):
    return {"id_orden": 15, "id_devolucion": 4, "id_bodega": id_bodega, "id_usuario": 7,
            "motivo": "Producto vencido", "items": items}


def kardex(id_bodega):
    with transaccion(CONFIG) as cur:
        cur.execute("SELECT * FROM movimientos WHERE id_bodega = %s ORDER BY id_movimiento", (id_bodega,))
        return cur.fetchall()


def saldo(sku, id_bodega):
    with transaccion(CONFIG) as cur:
        cur.execute("SELECT cantidad, costo_promedio FROM saldos WHERE sku = %s AND id_bodega = %s",
                    (sku, id_bodega))
        return cur.fetchone()


def procesado(id_evento):
    with transaccion(CONFIG) as cur:
        cur.execute("SELECT COUNT(*) AS n FROM eventos_procesados WHERE id_evento = %s", (id_evento,))
        return cur.fetchone()["n"] == 1


def test_mercancia_recibida_crea_entradas_con_costo_ponderado(bodega):
    procesar_evento(sobre("MercanciaRecibida", mercancia(bodega, [
        {"sku": "ZZTEST-EA", "cantidad": 10, "costo_unitario": 100}])))

    resultado = procesar_evento(sobre("MercanciaRecibida", mercancia(bodega, [
        {"sku": "zztest-ea", "cantidad": 5, "costo_unitario": 130},
        {"sku": "ZZTEST-EB", "cantidad": 3, "costo_unitario": 50}])))

    assert not resultado.ya_procesado and len(resultado.resultados) == 2
    filas = kardex(bodega)
    assert [f["tipo"] for f in filas] == ["ENTRADA_COMPRA"] * 3
    assert all(f["documento_referencia"] == "OC-15" for f in filas)
    assert all(f["motivo"] == "Recepción 31" and f["id_usuario"] == 7 for f in filas)
    assert saldo("ZZTEST-EA", bodega)["costo_promedio"] == D("110.0000")  # (10*100 + 5*130) / 15
    assert saldo("ZZTEST-EB", bodega)["cantidad"] == D("3")


def test_numero_de_la_orden_como_documento(bodega):
    procesar_evento(sobre("MercanciaRecibida", mercancia(bodega, [
        {"sku": "ZZTEST-EA", "cantidad": 1, "costo_unitario": 10}], numero="OC-2026-000099")))
    assert kardex(bodega)[0]["documento_referencia"] == "OC-2026-000099"


def test_devolucion_proveedor_crea_salida(bodega):
    procesar_evento(sobre("MercanciaRecibida", mercancia(bodega, [
        {"sku": "ZZTEST-EA", "cantidad": 10, "costo_unitario": 100}])))

    procesar_evento(sobre("DevolucionProveedorRegistrada", devolucion(bodega, [
        {"sku": "ZZTEST-EA", "cantidad": 4}])))

    ultima = kardex(bodega)[-1]
    assert ultima["tipo"] == "DEVOLUCION_PROVEEDOR" and ultima["documento_referencia"] == "OC-15"
    assert ultima["motivo"] == "Producto vencido"
    assert saldo("ZZTEST-EA", bodega)["cantidad"] == D("6")


def test_el_mismo_evento_solo_se_aplica_una_vez(bodega):
    id_evento = nuevo_id()
    cuerpo = sobre("MercanciaRecibida", mercancia(bodega, [
        {"sku": "ZZTEST-EA", "cantidad": 10, "costo_unitario": 100}]), id_evento=id_evento)

    primero = procesar_evento(cuerpo)
    segundo = procesar_evento(cuerpo)

    assert not primero.ya_procesado and segundo.ya_procesado and segundo.resultados == []
    assert saldo("ZZTEST-EA", bodega)["cantidad"] == D("10") and len(kardex(bodega)) == 1


def test_stock_insuficiente_no_deja_nada(bodega):
    procesar_evento(sobre("MercanciaRecibida", mercancia(bodega, [
        {"sku": "ZZTEST-EA", "cantidad": 2, "costo_unitario": 100}])))
    id_evento = nuevo_id()

    with pytest.raises(ApiError) as info:
        procesar_evento(sobre("DevolucionProveedorRegistrada", devolucion(bodega, [
            {"sku": "ZZTEST-EA", "cantidad": 1}, {"sku": "ZZTEST-EA", "cantidad": 5}]), id_evento=id_evento))

    assert info.value.codigo == "STOCK_INSUFICIENTE"
    assert len(kardex(bodega)) == 1 and saldo("ZZTEST-EA", bodega)["cantidad"] == D("2")
    assert not procesado(id_evento)


def test_un_sku_inexistente_hace_fallar_todo_el_evento(bodega, entorno):
    with pytest.raises(ApiError) as info:
        procesar_evento(sobre("MercanciaRecibida", mercancia(bodega, [
            {"sku": "ZZTEST-EA", "cantidad": 1, "costo_unitario": 10},
            {"sku": "ZZTEST-NOEXISTE", "cantidad": 1, "costo_unitario": 10}])))

    assert info.value.codigo == "PRODUCTO_INEXISTENTE"
    assert kardex(bodega) == []


@pytest.mark.parametrize("cuerpo", [
    b"{no es json",
    json.dumps({"id_evento": str(uuid.uuid4()), "tipo": "OrdenCompraActualizada", "datos": {}}).encode(),
    json.dumps({"id_evento": "no-es-uuid", "tipo": "MercanciaRecibida", "datos": {}}).encode(),
    json.dumps({"id_evento": str(uuid.uuid4()), "tipo": "MercanciaRecibida", "datos": {
        "id_orden": 1, "id_recepcion": 1, "id_bodega": 1, "id_usuario": 1, "items": []}}).encode(),
    json.dumps({"id_evento": str(uuid.uuid4()), "tipo": "MercanciaRecibida", "datos": {
        "id_orden": 1, "id_recepcion": 1, "id_bodega": 1, "id_usuario": 1,
        "items": [{"sku": "ZZTEST-EA", "cantidad": "2", "costo_unitario": 1}]}}).encode(),
])
def test_sobre_invalido(cuerpo, entorno):
    with pytest.raises(EventoInvalido):
        procesar_evento(cuerpo)
    assert entorno == []  # no se llegó a consultar ms-productos


def test_numeros_como_decimal_exacto_y_correlacion_del_evento(bodega, entorno):
    cuerpo = ('{"id_evento": "%s", "tipo": "MercanciaRecibida", "id_correlacion": "corr-xyz",'
              ' "datos": {"id_orden": 9, "id_recepcion": 2, "id_bodega": %d, "id_usuario": 7,'
              ' "items": [{"sku": "ZZTEST-EA", "cantidad": 2.5, "costo_unitario": 3150.12}]}}'
              % (nuevo_id(), bodega)).encode()

    resultado = procesar_evento(cuerpo)

    movimiento = resultado.resultados[0]["movimiento"]
    assert movimiento["cantidad"] == D("2.500") and movimiento["costo_unitario"] == D("3150.1200")
    assert resultado.id_correlacion == "corr-xyz"
    assert entorno == [("ZZTEST-EA", "corr-xyz")]
