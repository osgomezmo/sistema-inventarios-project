"""Pruebas de devoluciones de cliente (D47) contra el MySQL de desarrollo.

consultar_producto se reemplaza por un falso (no depende de ms-productos).
Bodegas con prefijo "ZZT-" y SKU "ZZTEST-", borrados al terminar solo por
esos prefijos. Si MySQL no está disponible, las pruebas se saltan.
"""

from decimal import Decimal as D

import pytest

import app.eventos as eventos
import app.routes.devoluciones as rutas
from app import create_app
from app.config import cargar_configuracion
from app.db import abrir_conexion, transaccion
from app.errors import ApiError
from app.servicios.movimientos import aplicar_movimiento

TOKEN = "token-de-prueba"
CABECERAS = {"Authorization": f"Bearer {TOKEN}", "X-User-Id": "7"}
SKU = "ZZTEST-D"
CAMPOS = {
    "id_movimiento", "sku", "id_bodega", "tipo", "cantidad", "costo_unitario",
    "saldo_resultante", "costo_promedio", "valor_resultante", "motivo",
    "documento_referencia", "id_usuario", "fecha",
}
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


@pytest.fixture(autouse=True)
def producto_falso(monkeypatch):
    monkeypatch.setattr(rutas, "consultar_producto", lambda sku, id_correlacion=None: {
        "sku": SKU, "nombre": "Producto", "estado": "ACTIVO", "unidad_medida": "UNIDAD",
        "stock_minimo": D("0"), "id_categoria": 1})
    monkeypatch.setattr(eventos, "publicar_movimiento", lambda *a, **k: None)


@pytest.fixture
def cliente():
    return create_app({"TESTING": True, "SERVICE_TOKEN": TOKEN}).test_client()


def crear_bodega(codigo="B1", estado="ACTIVO"):
    with transaccion(CONFIG) as cur:
        cur.execute("INSERT INTO bodegas (codigo, nombre, direccion, estado) VALUES (%s, %s, %s, %s)",
                    ("ZZT-" + codigo, codigo, "Calle 1", estado))
        return cur.lastrowid


@pytest.fixture
def bodega():
    """Bodega con 10 unidades a 80.0000."""
    id_bodega = crear_bodega()
    with transaccion(CONFIG) as cur:
        aplicar_movimiento(cur, sku=SKU, id_bodega=id_bodega, tipo="ENTRADA_COMPRA",
                           cantidad=D("10"), id_usuario=1, unidad_medida="UNIDAD",
                           stock_minimo=D("0"), costo_unitario=D("80.0000"))
    return id_bodega


def devolver(cliente, id_bodega, cabeceras=CABECERAS, **cambios):
    cuerpo = {"sku": SKU, "id_bodega": id_bodega, "cantidad": 2,
              "factura_pos": " POS-0001 ", "motivo": "Producto en mal estado"}
    cuerpo.update(cambios)
    return cliente.post("/devoluciones-cliente", headers=cabeceras, json=cuerpo)


def verificar_error(respuesta, status, codigo):
    assert respuesta.status_code == status, respuesta.get_json()
    error = respuesta.get_json()["error"]
    assert set(error) == {"codigo", "mensaje", "detalles"}
    assert error["codigo"] == codigo
    return error


def test_devolucion_correcta(cliente, bodega):
    respuesta = devolver(cliente, bodega)
    assert respuesta.status_code == 201
    movimiento = respuesta.get_json()
    assert set(movimiento) == CAMPOS
    assert movimiento["tipo"] == "DEVOLUCION_CLIENTE"
    assert movimiento["documento_referencia"] == "POS-0001"
    assert movimiento["motivo"] == "Producto en mal estado"
    assert (movimiento["costo_unitario"], movimiento["costo_promedio"]) == (80, 80)
    assert (movimiento["saldo_resultante"], movimiento["valor_resultante"]) == (12, 960)


def test_campos_faltantes_juntos(cliente, bodega):
    respuesta = cliente.post("/devoluciones-cliente", headers=CABECERAS, json={"sku": SKU})
    error = verificar_error(respuesta, 422, "VALIDACION")
    assert set(error["detalles"]) == {"id_bodega", "cantidad", "factura_pos", "motivo"}


def test_producto_inexistente(cliente, bodega, monkeypatch):
    def falla(sku, id_correlacion=None):
        raise ApiError("PRODUCTO_INEXISTENTE", "El producto no existe.", 404)

    monkeypatch.setattr(rutas, "consultar_producto", falla)
    verificar_error(devolver(cliente, bodega), 404, "PRODUCTO_INEXISTENTE")


def test_bodega_inactiva(cliente):
    inactiva = crear_bodega("INA", estado="INACTIVO")
    error = verificar_error(devolver(cliente, inactiva), 422, "VALIDACION")
    assert list(error["detalles"]) == ["id_bodega"]


def test_x_user_id_y_token(cliente, bodega):
    verificar_error(devolver(cliente, bodega, cabeceras={"Authorization": f"Bearer {TOKEN}"}),
                    400, "PETICION_INVALIDA")
    verificar_error(devolver(cliente, bodega, cabeceras={"X-User-Id": "7"}), 401, "NO_AUTENTICADO")


def test_listado_solo_trae_devoluciones(cliente, bodega):
    ids = [devolver(cliente, bodega, factura_pos=f"POS-{i}").get_json()["id_movimiento"]
           for i in range(3)]
    with transaccion(CONFIG) as cur:  # otro tipo de movimiento del mismo SKU
        aplicar_movimiento(cur, sku=SKU, id_bodega=bodega, tipo="SALIDA", cantidad=D("1"),
                           id_usuario=1, unidad_medida="UNIDAD", stock_minimo=D("0"))
    todos = cliente.get("/movimientos", headers=CABECERAS, query_string={"sku": SKU}).get_json()
    assert todos["meta"]["total"] == 5  # entrada, 3 devoluciones y la salida

    cuerpo = cliente.get("/devoluciones-cliente", headers=CABECERAS,
                         query_string={"sku": "zztest-d"}).get_json()
    assert cuerpo["meta"]["total"] == 3
    assert [m["id_movimiento"] for m in cuerpo["data"]] == ids[::-1]
    assert {m["tipo"] for m in cuerpo["data"]} == {"DEVOLUCION_CLIENTE"}

    pagina = cliente.get("/devoluciones-cliente", headers=CABECERAS,
                         query_string={"sku": SKU, "per_page": 2, "page": 2}).get_json()
    assert [m["id_movimiento"] for m in pagina["data"]] == [ids[0]]
    otro = cliente.get("/devoluciones-cliente", headers=CABECERAS,
                       query_string={"sku": "ZZTEST-OTRO"}).get_json()
    assert otro["data"] == []
