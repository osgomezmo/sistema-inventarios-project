"""Pruebas de POST /bodegas/{id}/inactivar y /activar contra el MySQL de desarrollo.

Las bodegas de prueba llevan el prefijo de código PREFIJO y los saldos de apoyo
el prefijo de SKU PREFIJO_SKU. Un fixture borra al terminar solo esas filas:
primero saldos y luego bodegas. Si MySQL no está disponible, las pruebas se
saltan.
"""

import threading
from decimal import Decimal

import pytest

from app import create_app
from app.config import cargar_configuracion
from app.db import abrir_conexion, transaccion
from app.errors import ApiError
from app.repositorios import bodegas as repo_bodegas

PREFIJO = "ZZT-"
PREFIJO_SKU = "ZZTEST-"
TOKEN = "token-de-prueba"
CABECERAS = {"Authorization": f"Bearer {TOKEN}"}
CAMPOS = {"id_bodega", "codigo", "nombre", "direccion", "estado"}
CONFIG = cargar_configuracion()


def patron_like(prefijo):
    # En LIKE, "_" y "%" son comodines: se escapan para filtrar solo el prefijo exacto.
    return prefijo.replace("\\", "\\\\").replace("_", "\\_").replace("%", "\\%") + "%"


def borrar_datos_de_prueba():
    with transaccion(CONFIG) as cur:
        cur.execute("DELETE FROM saldos WHERE sku LIKE %s", (patron_like(PREFIJO_SKU),))
        cur.execute("DELETE FROM bodegas WHERE codigo LIKE %s", (patron_like(PREFIJO),))


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
def app():
    return create_app({"TESTING": True, "SERVICE_TOKEN": TOKEN})


@pytest.fixture
def cliente(app):
    return app.test_client()


def crear_bodega(codigo="EST", estado="ACTIVO"):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO bodegas (codigo, nombre, direccion, estado) VALUES (%s, %s, %s, %s)",
            (PREFIJO + codigo, "Bodega de prueba", "Calle 1 # 2-3", estado),
        )
        return cur.lastrowid


def crear_saldo(id_bodega, cantidad="25.000"):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO saldos (sku, id_bodega, cantidad, costo_promedio) VALUES (%s, %s, %s, %s)",
            (PREFIJO_SKU + "001", id_bodega, Decimal(cantidad), Decimal("3150.0000")),
        )
        return cur.lastrowid


def estado_sql(id_bodega):
    with transaccion(CONFIG) as cur:
        cur.execute("SELECT estado FROM bodegas WHERE id_bodega = %s", (id_bodega,))
        return cur.fetchone()["estado"]


def inactivar(cliente, id_bodega, **kwargs):
    return cliente.post(f"/bodegas/{id_bodega}/inactivar", headers=CABECERAS, **kwargs)


def activar(cliente, id_bodega, **kwargs):
    return cliente.post(f"/bodegas/{id_bodega}/activar", headers=CABECERAS, **kwargs)


def verificar_error(respuesta, status, codigo):
    assert respuesta.status_code == status, respuesta.get_json()
    error = respuesta.get_json()["error"]
    assert set(error) == {"codigo", "mensaje", "detalles"}
    assert error["codigo"] == codigo
    return error


@pytest.fixture
def contador_updates(monkeypatch):
    """Cuenta las llamadas a actualizar_estado sin cambiar su efecto."""
    llamadas = []
    original = repo_bodegas.actualizar_estado

    def contar(cursor, id_bodega, estado):
        llamadas.append((id_bodega, estado))
        return original(cursor, id_bodega, estado)

    monkeypatch.setattr(repo_bodegas, "actualizar_estado", contar)
    return llamadas


# --- Inactivar ----------------------------------------------------------------


def test_inactivar(cliente):
    id_bodega = crear_bodega()
    respuesta = inactivar(cliente, id_bodega)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "id_bodega": id_bodega,
        "codigo": "ZZT-EST",
        "nombre": "Bodega de prueba",
        "direccion": "Calle 1 # 2-3",
        "estado": "INACTIVO",
    }
    assert estado_sql(id_bodega) == "INACTIVO"
    otra = cliente.get(f"/bodegas/{id_bodega}", headers=CABECERAS).get_json()
    assert otra == respuesta.get_json()


def test_inactivar_dos_veces_es_idempotente(cliente, contador_updates):
    id_bodega = crear_bodega()
    primera = inactivar(cliente, id_bodega)
    segunda = inactivar(cliente, id_bodega)
    assert primera.status_code == segunda.status_code == 200
    assert primera.get_json() == segunda.get_json()
    assert contador_updates == [(id_bodega, "INACTIVO")]


def test_inactivar_bodega_con_saldo_es_valido(cliente):
    id_bodega = crear_bodega()
    id_saldo = crear_saldo(id_bodega)
    assert inactivar(cliente, id_bodega).status_code == 200
    with transaccion(CONFIG) as cur:
        cur.execute("SELECT cantidad FROM saldos WHERE id_saldo = %s", (id_saldo,))
        assert cur.fetchone()["cantidad"] == Decimal("25.000")


# --- Activar ------------------------------------------------------------------


def test_activar_bodega_inactiva(cliente):
    id_bodega = crear_bodega(estado="INACTIVO")
    respuesta = activar(cliente, id_bodega)
    assert respuesta.status_code == 200
    assert set(respuesta.get_json()) == CAMPOS
    assert respuesta.get_json()["estado"] == "ACTIVO"
    assert estado_sql(id_bodega) == "ACTIVO"


def test_activar_dos_veces_es_idempotente(cliente, contador_updates):
    id_bodega = crear_bodega(estado="INACTIVO")
    primera = activar(cliente, id_bodega)
    segunda = activar(cliente, id_bodega)
    assert primera.status_code == segunda.status_code == 200
    assert primera.get_json() == segunda.get_json()
    assert contador_updates == [(id_bodega, "ACTIVO")]


def test_activar_una_activa_responde_sin_cambios(cliente, contador_updates):
    id_bodega = crear_bodega()
    respuesta = activar(cliente, id_bodega)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["estado"] == "ACTIVO"
    assert contador_updates == []


# --- Errores comunes ----------------------------------------------------------


@pytest.mark.parametrize("accion", ["inactivar", "activar"])
def test_id_inexistente_da_404(cliente, accion):
    respuesta = cliente.post(f"/bodegas/999999999/{accion}", headers=CABECERAS)
    error = verificar_error(respuesta, 404, "NO_EXISTE")
    assert error["mensaje"] == "La bodega no existe."


@pytest.mark.parametrize("accion", ["inactivar", "activar"])
@pytest.mark.parametrize("id_ruta", ["abc", "-1", "1.5"])
def test_id_no_entero_da_404(cliente, accion, id_ruta):
    respuesta = cliente.post(f"/bodegas/{id_ruta}/{accion}", headers=CABECERAS)
    verificar_error(respuesta, 404, "NO_EXISTE")


@pytest.mark.parametrize("accion", ["inactivar", "activar"])
def test_sin_token_da_401(cliente, accion):
    id_bodega = crear_bodega(estado="INACTIVO" if accion == "activar" else "ACTIVO")
    antes = estado_sql(id_bodega)
    verificar_error(cliente.post(f"/bodegas/{id_bodega}/{accion}"), 401, "NO_AUTENTICADO")
    assert estado_sql(id_bodega) == antes


@pytest.mark.parametrize(
    "kwargs",
    [
        {"json": {"estado": "ACTIVO", "codigo": "OTRO"}},
        {"data": "no es json", "content_type": "text/plain"},
        {"data": "[1, 2]", "content_type": "application/json"},
    ],
)
def test_el_cuerpo_se_ignora(cliente, kwargs):
    id_bodega = crear_bodega()
    respuesta = inactivar(cliente, id_bodega, **kwargs)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["estado"] == "INACTIVO"
    assert respuesta.get_json()["codigo"] == "ZZT-EST"
    respuesta = activar(cliente, id_bodega, **kwargs)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["estado"] == "ACTIVO"


@pytest.mark.parametrize("accion", ["inactivar", "activar"])
def test_get_no_permitido_da_405(cliente, accion):
    respuesta = cliente.get(f"/bodegas/1/{accion}", headers=CABECERAS)
    verificar_error(respuesta, 405, "METODO_NO_PERMITIDO")


# --- Integración con lectura y edición -----------------------------------------


def test_listado_por_estado_refleja_el_cambio(cliente):
    id_bodega = crear_bodega()
    inactivar(cliente, id_bodega)
    cuerpo = cliente.get(
        "/bodegas", headers=CABECERAS, query_string={"estado": "INACTIVO", "per_page": 100}
    ).get_json()
    assert id_bodega in [b["id_bodega"] for b in cuerpo["data"]]

    activar(cliente, id_bodega)
    cuerpo = cliente.get(
        "/bodegas", headers=CABECERAS, query_string={"estado": "INACTIVO", "per_page": 100}
    ).get_json()
    assert id_bodega not in [b["id_bodega"] for b in cuerpo["data"]]


def test_put_de_bodega_inactiva_la_deja_inactiva(cliente):
    id_bodega = crear_bodega()
    inactivar(cliente, id_bodega)
    respuesta = cliente.put(
        f"/bodegas/{id_bodega}", headers=CABECERAS,
        json={"nombre": "Renombrada", "direccion": "Otra", "estado": "ACTIVO"},
    )
    assert respuesta.status_code == 200
    assert respuesta.get_json()["estado"] == "INACTIVO"
    assert estado_sql(id_bodega) == "INACTIVO"


# --- Concurrencia ---------------------------------------------------------------


@pytest.mark.parametrize("ronda", range(10))
def test_concurrencia_inactivar_y_activar(app, ronda):
    id_bodega = crear_bodega(f"CONC-{ronda}")
    barrera = threading.Barrier(2)
    resultados = {}

    def ejecutar(accion):
        cliente = app.test_client()
        barrera.wait()
        respuesta = cliente.post(f"/bodegas/{id_bodega}/{accion}", headers=CABECERAS)
        resultados[accion] = (respuesta.status_code, respuesta.get_json()["estado"])

    hilos = [threading.Thread(target=ejecutar, args=(a,)) for a in ("inactivar", "activar")]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    # Las dos terminan bien y cada una responde el estado que dejó.
    assert resultados["inactivar"] == (200, "INACTIVO")
    assert resultados["activar"] == (200, "ACTIVO")
    # El estado final es el de la que se aplicó de última, y coincide con lo que lee GET.
    final = estado_sql(id_bodega)
    assert final in ("ACTIVO", "INACTIVO")
    consultada = app.test_client().get(f"/bodegas/{id_bodega}", headers=CABECERAS)
    assert consultada.get_json()["estado"] == final
