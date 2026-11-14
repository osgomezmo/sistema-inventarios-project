"""Pruebas de POST /movimientos (D44) contra el MySQL de desarrollo.

consultar_producto se reemplaza por un falso, así que no dependen de que
ms-productos esté arriba. Las bodegas usan el prefijo "ZZT-" y los SKU
"ZZTEST-"; un fixture borra al terminar solo esas filas. Si MySQL no está
disponible, las pruebas se saltan.
"""

import threading
from decimal import Decimal as D

import pytest

import app.eventos as eventos
import app.routes.movimientos as rutas
from app import create_app
from app.config import cargar_configuracion
from app.db import abrir_conexion, transaccion
from app.errors import ApiError
from app.servicios.movimientos import aplicar_movimiento, costo_ponderado

TOKEN = "token-de-prueba"
CABECERAS = {"Authorization": f"Bearer {TOKEN}", "X-User-Id": "7"}
CAMPOS = {
    "id_movimiento", "sku", "id_bodega", "tipo", "cantidad", "costo_unitario",
    "saldo_resultante", "costo_promedio", "valor_resultante", "motivo",
    "documento_referencia", "id_usuario", "fecha",
}
SKU = "ZZTEST-A"
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
def consultas(monkeypatch):
    """Producto falso: siempre devuelve el SKU canónico ZZTEST-A, UNIDAD, mínimo 2."""
    pedidos = []

    def falso(sku, id_correlacion=None):
        pedidos.append((sku, id_correlacion))
        return {"sku": SKU, "nombre": "Producto", "estado": "ACTIVO",
                "unidad_medida": "UNIDAD", "stock_minimo": D("2"), "id_categoria": 1}

    monkeypatch.setattr(rutas, "consultar_producto", falso)
    return pedidos


@pytest.fixture
def avisos(monkeypatch):
    llamadas = []
    monkeypatch.setattr(eventos, "publicar_movimiento",
                        lambda resultado, id_correlacion=None: llamadas.append(resultado))
    return llamadas


@pytest.fixture
def app(consultas, avisos):
    return create_app({"TESTING": True, "SERVICE_TOKEN": TOKEN})


@pytest.fixture
def cliente(app):
    return app.test_client()


def crear_bodega(codigo="B1", estado="ACTIVO"):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO bodegas (codigo, nombre, direccion, estado) VALUES (%s, %s, %s, %s)",
            ("ZZT-" + codigo, f"Bodega {codigo}", "Calle 1", estado),
        )
        return cur.lastrowid


@pytest.fixture
def bodega():
    """Bodega con 10 unidades de ZZTEST-A a 100.0000."""
    id_bodega = crear_bodega()
    with transaccion(CONFIG) as cur:
        aplicar_movimiento(cur, sku=SKU, id_bodega=id_bodega, tipo="ENTRADA_COMPRA",
                           cantidad=D("10"), id_usuario=1, unidad_medida="UNIDAD",
                           stock_minimo=D("2"), costo_unitario=D("100.0000"))
    return id_bodega


def saldo(id_bodega):
    with transaccion(CONFIG) as cur:
        cur.execute("SELECT cantidad, costo_promedio FROM saldos WHERE sku = %s AND id_bodega = %s",
                    (SKU, id_bodega))
        return cur.fetchone()


def kardex(id_bodega):
    with transaccion(CONFIG) as cur:
        cur.execute("SELECT * FROM movimientos WHERE sku = %s AND id_bodega = %s"
                    " ORDER BY id_movimiento", (SKU, id_bodega))
        return cur.fetchall()


def post(cliente, cuerpo, cabeceras=CABECERAS, **kwargs):
    return cliente.post("/movimientos", headers=cabeceras, json=cuerpo, **kwargs)


def cuerpo(id_bodega, **cambios):
    datos = {"sku": SKU, "id_bodega": id_bodega, "tipo": "SALIDA", "cantidad": 3}
    datos.update(cambios)
    return datos


def verificar_error(respuesta, status, codigo):
    assert respuesta.status_code == status, respuesta.get_json()
    error = respuesta.get_json()["error"]
    assert set(error) == {"codigo", "mensaje", "detalles"}
    assert error["codigo"] == codigo
    return error


# --- Camino feliz -----------------------------------------------------------------


def test_salida(cliente, bodega, avisos):
    respuesta = post(cliente, cuerpo(bodega, documento_referencia="POS-1"))
    assert respuesta.status_code == 201
    movimiento = respuesta.get_json()
    assert set(movimiento) == CAMPOS
    assert movimiento["tipo"] == "SALIDA" and movimiento["id_usuario"] == 7
    assert (movimiento["cantidad"], movimiento["saldo_resultante"]) == (3, 7)
    assert movimiento["costo_promedio"] == 100 and movimiento["valor_resultante"] == 700
    assert movimiento["documento_referencia"] == "POS-1"
    assert saldo(bodega)["cantidad"] == D("7") and saldo(bodega)["costo_promedio"] == D("100")
    assert len(avisos) == 1


def test_ajuste_positivo_con_y_sin_costo(cliente, bodega):
    con_costo = post(cliente, cuerpo(bodega, tipo="AJUSTE_POSITIVO", cantidad=10,
                                     costo_unitario="200", motivo="Conteo")).get_json()
    assert (con_costo["saldo_resultante"], con_costo["costo_promedio"]) == (20, 150)
    sin_costo = post(cliente, cuerpo(bodega, tipo="AJUSTE_POSITIVO", cantidad=5,
                                     motivo="Conteo")).get_json()
    assert sin_costo["costo_unitario"] == 150 and sin_costo["costo_promedio"] == 150


def test_ajuste_negativo(cliente, bodega):
    movimiento = post(cliente, cuerpo(bodega, tipo="AJUSTE_NEGATIVO", cantidad=4,
                                      motivo="Merma")).get_json()
    assert movimiento["saldo_resultante"] == 6 and movimiento["motivo"] == "Merma"


def test_guarda_el_sku_canonico(cliente, bodega, consultas):
    respuesta = post(cliente, cuerpo(bodega, sku="zztest-a"))
    assert respuesta.status_code == 201
    assert respuesta.get_json()["sku"] == SKU
    assert consultas[-1][0] == SKU  # se consultó ya normalizado
    alias = post(cliente, cuerpo(bodega, sku="ZZTEST-ALIAS"))
    assert alias.get_json()["sku"] == SKU  # se guarda lo que devuelve ms-productos


def test_reenvia_la_correlacion(cliente, bodega, consultas):
    post(cliente, cuerpo(bodega), cabeceras={**CABECERAS, "X-Correlation-Id": "corr-1"})
    assert consultas[-1] == (SKU, "corr-1")


# --- Errores --------------------------------------------------------------------------


def test_salida_mayor_que_el_saldo(cliente, bodega, avisos):
    verificar_error(post(cliente, cuerpo(bodega, cantidad=11)), 409, "STOCK_INSUFICIENTE")
    assert saldo(bodega)["cantidad"] == D("10") and len(kardex(bodega)) == 1
    assert avisos == []


def test_ajuste_sin_motivo(cliente, bodega):
    error = verificar_error(post(cliente, cuerpo(bodega, tipo="AJUSTE_NEGATIVO")), 422, "VALIDACION")
    assert list(error["detalles"]) == ["motivo"]


def test_varios_errores_juntos(cliente, bodega, consultas):
    respuesta = post(cliente, {"sku": "MAL SKU", "id_bodega": "x", "tipo": "ENTRADA_COMPRA",
                               "cantidad": 0, "costo_unitario": "1.00001"})
    error = verificar_error(respuesta, 422, "VALIDACION")
    assert set(error["detalles"]) == {"sku", "id_bodega", "tipo", "cantidad", "costo_unitario"}
    assert consultas == []


def test_cuerpo_que_no_es_json(cliente, bodega):
    respuesta = cliente.post("/movimientos", headers=CABECERAS, data="x", content_type="text/plain")
    verificar_error(respuesta, 400, "PETICION_INVALIDA")


@pytest.mark.parametrize("id_usuario", [None, "", "abc", "0", "-1", "1.5"])
def test_x_user_id_ausente_o_invalido(cliente, bodega, id_usuario):
    cabeceras = {"Authorization": f"Bearer {TOKEN}"}
    if id_usuario is not None:
        cabeceras["X-User-Id"] = id_usuario
    verificar_error(post(cliente, cuerpo(bodega), cabeceras=cabeceras), 400, "PETICION_INVALIDA")
    assert len(kardex(bodega)) == 1


def test_sin_token(cliente, bodega):
    verificar_error(post(cliente, cuerpo(bodega), cabeceras={"X-User-Id": "7"}), 401, "NO_AUTENTICADO")


def test_bodega_inexistente_e_inactiva(cliente):
    verificar_error(post(cliente, cuerpo(999_999_999)), 404, "NO_EXISTE")
    inactiva = crear_bodega("INA", estado="INACTIVO")
    error = verificar_error(post(cliente, cuerpo(inactiva, tipo="AJUSTE_POSITIVO",
                                                 costo_unitario=1, motivo="x")), 422, "VALIDACION")
    assert list(error["detalles"]) == ["id_bodega"]


@pytest.mark.parametrize(
    "error_api",
    [ApiError("PRODUCTO_INEXISTENTE", "El producto no existe.", 404),
     ApiError("SERVICIO_NO_DISPONIBLE", "El servicio de productos no responde.", 503)],
)
def test_fallas_de_ms_productos_no_tocan_la_base(cliente, bodega, monkeypatch, avisos, error_api):
    def falla(sku, id_correlacion=None):
        raise error_api

    monkeypatch.setattr(rutas, "consultar_producto", falla)
    verificar_error(post(cliente, cuerpo(bodega)), error_api.status, error_api.codigo)
    assert saldo(bodega)["cantidad"] == D("10") and len(kardex(bodega)) == 1
    assert avisos == []


def test_si_el_gancho_falla_la_respuesta_sigue_siendo_201(cliente, bodega, monkeypatch):
    def gancho_roto(resultado, id_correlacion=None):
        raise RuntimeError("falla del gancho")

    monkeypatch.setattr(eventos, "publicar_movimiento", gancho_roto)
    assert post(cliente, cuerpo(bodega)).status_code == 201
    assert saldo(bodega)["cantidad"] == D("7")


# --- Concurrencia por HTTP ---------------------------------------------------------------


@pytest.mark.parametrize("ronda", range(3))
def test_concurrencia_de_salidas(app, bodega, ronda):
    barrera = threading.Barrier(20)
    codigos = []

    def salir():
        cliente = app.test_client()
        barrera.wait()
        codigos.append(post(cliente, cuerpo(bodega, cantidad=1)).status_code)

    hilos = [threading.Thread(target=salir) for _ in range(20)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert sorted(codigos) == [201] * 10 + [409] * 10
    assert saldo(bodega)["cantidad"] == 0
    filas = kardex(bodega)
    assert len(filas) == 11
    previo, costo = D("0"), D("0")
    for fila in filas:
        if fila["tipo"] == "ENTRADA_COMPRA":
            assert fila["saldo_resultante"] == previo + fila["cantidad"]
            assert fila["costo_promedio"] == costo_ponderado(
                previo, costo, fila["cantidad"], fila["costo_unitario"])
        else:
            assert fila["saldo_resultante"] == previo - fila["cantidad"]
            assert fila["costo_promedio"] == costo
        previo, costo = fila["saldo_resultante"], fila["costo_promedio"]
