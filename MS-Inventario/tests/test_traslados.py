"""Pruebas de traslados (D46) contra el MySQL de desarrollo.

consultar_producto se reemplaza por un falso (no depende de ms-productos).
Bodegas con prefijo "ZZT-" y SKU "ZZTEST-", borrados al terminar solo por
esos prefijos. Si MySQL no está disponible, las pruebas se saltan.
"""

import threading
from decimal import Decimal as D

import pytest

import app.eventos as eventos
import app.routes.traslados as rutas
from app import create_app
from app.config import cargar_configuracion
from app.db import abrir_conexion, transaccion
from app.errors import ApiError
from app.servicios.movimientos import aplicar_movimiento

TOKEN = "token-de-prueba"
CABECERAS = {"Authorization": f"Bearer {TOKEN}", "X-User-Id": "7"}
SKU = "ZZTEST-T"
CAMPOS = {"id_traslado", "sku", "id_bodega_origen", "id_bodega_destino", "cantidad", "motivo",
          "id_usuario", "fecha", "movimientos"}
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


@pytest.fixture
def avisos(monkeypatch):
    llamadas = []
    monkeypatch.setattr(eventos, "publicar_movimiento",
                        lambda resultado, id_correlacion=None: llamadas.append(resultado))
    return llamadas


@pytest.fixture
def app():
    return create_app({"TESTING": True, "SERVICE_TOKEN": TOKEN})


@pytest.fixture
def cliente(app):
    return app.test_client()


def crear_bodega(codigo, estado="ACTIVO"):
    with transaccion(CONFIG) as cur:
        cur.execute("INSERT INTO bodegas (codigo, nombre, direccion, estado) VALUES (%s, %s, %s, %s)",
                    ("ZZT-" + codigo, codigo, "Calle 1", estado))
        return cur.lastrowid


def entrada(id_bodega, cantidad, costo):
    with transaccion(CONFIG) as cur:
        aplicar_movimiento(cur, sku=SKU, id_bodega=id_bodega, tipo="ENTRADA_COMPRA",
                           cantidad=D(cantidad), id_usuario=1, unidad_medida="UNIDAD",
                           stock_minimo=D("0"), costo_unitario=D(costo))


@pytest.fixture
def bodegas():
    """A con 10 a 100.0000 y B con 10 a 50.0000."""
    a, b = crear_bodega("A"), crear_bodega("B")
    entrada(a, "10", "100.0000")
    entrada(b, "10", "50.0000")
    return a, b


def saldo(id_bodega):
    with transaccion(CONFIG) as cur:
        cur.execute("SELECT cantidad, costo_promedio FROM saldos WHERE sku = %s AND id_bodega = %s",
                    (SKU, id_bodega))
        return cur.fetchone()


def contar(tabla):
    with transaccion(CONFIG) as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM {tabla} WHERE sku LIKE %s", ("ZZTEST-%",))
        return cur.fetchone()["n"]


def trasladar(cliente, origen, destino, cantidad=2, cabeceras=CABECERAS, **extra):
    cuerpo = {"sku": SKU, "id_bodega_origen": origen, "id_bodega_destino": destino,
              "cantidad": cantidad, **extra}
    return cliente.post("/traslados", headers=cabeceras, json=cuerpo)


def verificar_error(respuesta, status, codigo):
    assert respuesta.status_code == status, respuesta.get_json()
    error = respuesta.get_json()["error"]
    assert set(error) == {"codigo", "mensaje", "detalles"}
    assert error["codigo"] == codigo
    return error


# --- POST /traslados ----------------------------------------------------------------


def test_traslado_correcto(cliente, bodegas, avisos):
    a, b = bodegas
    respuesta = trasladar(cliente, a, b, cantidad=5, motivo="Reposición")
    assert respuesta.status_code == 201
    traslado = respuesta.get_json()
    assert set(traslado) == CAMPOS
    assert (traslado["cantidad"], traslado["motivo"], traslado["id_usuario"]) == (5, "Reposición", 7)

    assert saldo(a)["cantidad"] == D("5") and saldo(a)["costo_promedio"] == D("100")
    # Destino ponderado: (10 * 50 + 5 * 100) / 15 = 66.6667
    assert saldo(b)["cantidad"] == D("15") and saldo(b)["costo_promedio"] == D("66.6667")

    with transaccion(CONFIG) as cur:
        cur.execute("SELECT id_movimiento, tipo, id_bodega, costo_unitario, documento_referencia,"
                    " motivo, id_traslado FROM movimientos WHERE id_traslado = %s"
                    " ORDER BY id_movimiento", (traslado["id_traslado"],))
        salida, llegada = cur.fetchall()
    assert traslado["movimientos"] == {"salida": salida["id_movimiento"],
                                       "entrada": llegada["id_movimiento"]}
    assert (salida["tipo"], salida["id_bodega"]) == ("TRASLADO_SALIDA", a)
    assert (llegada["tipo"], llegada["id_bodega"]) == ("TRASLADO_ENTRADA", b)
    assert llegada["costo_unitario"] == D("100")
    documento = f"TR-{traslado['id_traslado']}"
    assert salida["documento_referencia"] == llegada["documento_referencia"] == documento
    assert salida["motivo"] == llegada["motivo"] == "Reposición"
    assert len(avisos) == 2


def test_stock_insuficiente_no_cambia_nada(cliente, bodegas, avisos):
    a, b = bodegas
    verificar_error(trasladar(cliente, a, b, cantidad=11), 409, "STOCK_INSUFICIENTE")
    assert saldo(a)["cantidad"] == D("10") and saldo(b)["cantidad"] == D("10")
    assert contar("traslados") == 0 and contar("movimientos") == 2
    assert avisos == []


def test_origen_sin_saldo_no_crea_saldos(cliente):
    a, b = crear_bodega("A"), crear_bodega("B")
    verificar_error(trasladar(cliente, b, a), 409, "STOCK_INSUFICIENTE")
    assert saldo(a) is None and saldo(b) is None and contar("traslados") == 0


def test_bodegas_iguales(cliente, bodegas):
    error = verificar_error(trasladar(cliente, bodegas[0], bodegas[0]), 422, "VALIDACION")
    assert list(error["detalles"]) == ["id_bodega_destino"]


def test_bodega_inactiva_e_inexistente(cliente, bodegas):
    a, _ = bodegas
    inactiva = crear_bodega("INA", estado="INACTIVO")
    error = verificar_error(trasladar(cliente, a, inactiva), 422, "VALIDACION")
    assert list(error["detalles"]) == ["id_bodega_destino"]
    error = verificar_error(trasladar(cliente, 999_999_999, a), 404, "NO_EXISTE")
    assert list(error["detalles"]) == ["id_bodega_origen"]


@pytest.mark.parametrize("error_api", [
    ApiError("PRODUCTO_INEXISTENTE", "El producto no existe.", 404),
    ApiError("SERVICIO_NO_DISPONIBLE", "El servicio de productos no responde.", 503),
])
def test_fallas_de_ms_productos(cliente, bodegas, monkeypatch, error_api):
    def falla(sku, id_correlacion=None):
        raise error_api

    monkeypatch.setattr(rutas, "consultar_producto", falla)
    verificar_error(trasladar(cliente, *bodegas), error_api.status, error_api.codigo)
    assert contar("traslados") == 0


def test_x_user_id_y_token(cliente, bodegas):
    verificar_error(trasladar(cliente, *bodegas, cabeceras={"Authorization": f"Bearer {TOKEN}"}),
                    400, "PETICION_INVALIDA")
    verificar_error(trasladar(cliente, *bodegas, cabeceras={"X-User-Id": "7"}), 401, "NO_AUTENTICADO")


# --- Lectura -------------------------------------------------------------------------------


def test_listado_y_consulta(cliente, bodegas):
    a, b = bodegas
    primero = trasladar(cliente, a, b, cantidad=1).get_json()
    segundo = trasladar(cliente, b, a, cantidad=1).get_json()

    cuerpo = cliente.get("/traslados", headers=CABECERAS,
                         query_string={"sku": "zztest-t"}).get_json()
    assert cuerpo["meta"]["total"] == 2
    assert [t["id_traslado"] for t in cuerpo["data"]] == [segundo["id_traslado"], primero["id_traslado"]]
    assert cuerpo["data"][1]["movimientos"] == primero["movimientos"]
    assert all(set(t) == CAMPOS for t in cuerpo["data"])
    assert cliente.get("/traslados", headers=CABECERAS,
                       query_string={"sku": "ZZTEST-OTRO"}).get_json()["data"] == []

    por_id = cliente.get(f"/traslados/{primero['id_traslado']}", headers=CABECERAS)
    assert por_id.status_code == 200 and por_id.get_json() == primero
    error = verificar_error(cliente.get("/traslados/999999999", headers=CABECERAS), 404, "NO_EXISTE")
    assert error["mensaje"] == "El traslado no existe."


# --- Concurrencia ------------------------------------------------------------------------------


@pytest.mark.parametrize("ronda", range(3))
def test_traslados_cruzados_simultaneos(app, ronda):
    a, b = crear_bodega("A"), crear_bodega("B")
    entrada(a, "20", "10.0000")
    entrada(b, "20", "30.0000")
    barrera = threading.Barrier(20)
    codigos = []

    def mover(origen, destino):
        cliente = app.test_client()
        barrera.wait()
        codigos.append(trasladar(cliente, origen, destino, cantidad=1).status_code)

    hilos = [threading.Thread(target=mover, args=(a, b)) for _ in range(10)]
    hilos += [threading.Thread(target=mover, args=(b, a)) for _ in range(10)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert 500 not in codigos and set(codigos) <= {201, 409}, codigos
    assert saldo(a)["cantidad"] + saldo(b)["cantidad"] == D("40")
    assert contar("traslados") == codigos.count(201)
