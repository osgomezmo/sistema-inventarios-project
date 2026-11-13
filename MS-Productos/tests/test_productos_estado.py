"""Pruebas de POST /productos/{id}/inactivar y /activar contra el MySQL de desarrollo.

Los productos de prueba llevan el prefijo de SKU PREFIJO_SKU y las categorías el
prefijo de nombre PREFIJO. Un fixture borra al terminar solo esas filas:
primero productos, luego subcategorías y al final raíces. Si MySQL no está
disponible, las pruebas se saltan.
"""

import json
import threading

import pytest

from app import create_app
from app.config import cargar_configuracion
from app.db import abrir_conexion, transaccion
from app.errors import ApiError
from app.repositorios import productos as repo_productos

PREFIJO = "zz_test_"
PREFIJO_SKU = "ZZTEST-"
TOKEN = "token-de-prueba"
CABECERAS = {"Authorization": f"Bearer {TOKEN}"}
CAMPOS = {
    "id_producto", "sku", "nombre", "descripcion", "marca", "id_categoria",
    "unidad_medida", "precio_venta", "stock_minimo", "estado",
}
CONFIG = cargar_configuracion()


def patron_like(prefijo):
    # En LIKE, "_" y "%" son comodines: se escapan para filtrar solo el prefijo exacto.
    return prefijo.replace("\\", "\\\\").replace("_", "\\_").replace("%", "\\%") + "%"


def borrar_datos_de_prueba():
    with transaccion(CONFIG) as cur:
        cur.execute("DELETE FROM productos WHERE sku LIKE %s", (patron_like(PREFIJO_SKU),))
        patron = patron_like(PREFIJO)
        cur.execute(
            "DELETE FROM categorias WHERE nombre LIKE %s AND id_categoria_padre IS NOT NULL",
            (patron,),
        )
        cur.execute(
            "DELETE FROM categorias WHERE nombre LIKE %s AND id_categoria_padre IS NULL",
            (patron,),
        )


@pytest.fixture(scope="module", autouse=True)
def mysql_disponible():
    try:
        abrir_conexion(CONFIG).close()
    except ApiError:
        pytest.skip("MySQL de desarrollo no disponible en 127.0.0.1:33061")


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


def crear_categoria(nombre, estado="ACTIVO"):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO categorias (nombre, estado) VALUES (%s, %s)", (PREFIJO + nombre, estado)
        )
        return cur.lastrowid


def crear_producto(sku, id_categoria, estado="ACTIVO"):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO productos (sku, nombre, marca, id_categoria, unidad_medida,"
            " precio_venta, stock_minimo, estado) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (PREFIJO_SKU + sku, "Producto de prueba", "Marca", id_categoria, "KILO",
             "1500.50", "2.250", estado),
        )
        return cur.lastrowid


def cambiar_estado_categoria(id_categoria, estado):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "UPDATE categorias SET estado = %s WHERE id_categoria = %s", (estado, id_categoria)
        )


def estado_producto(id_producto):
    with transaccion(CONFIG) as cur:
        cur.execute("SELECT estado FROM productos WHERE id_producto = %s", (id_producto,))
        return cur.fetchone()["estado"]


def estado_categoria(id_categoria):
    with transaccion(CONFIG) as cur:
        cur.execute("SELECT estado FROM categorias WHERE id_categoria = %s", (id_categoria,))
        return cur.fetchone()["estado"]


def inactivar(cliente, id_producto, **kwargs):
    return cliente.post(f"/productos/{id_producto}/inactivar", headers=CABECERAS, **kwargs)


def activar(cliente, id_producto, **kwargs):
    return cliente.post(f"/productos/{id_producto}/activar", headers=CABECERAS, **kwargs)


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
    original = repo_productos.actualizar_estado

    def contar(cursor, id_producto, estado):
        llamadas.append((id_producto, estado))
        return original(cursor, id_producto, estado)

    monkeypatch.setattr(repo_productos, "actualizar_estado", contar)
    return llamadas


@pytest.fixture
def categoria():
    return crear_categoria("raiz")


# --- Inactivar ----------------------------------------------------------------


def test_inactivar(cliente, categoria):
    id_producto = crear_producto("001", categoria)
    respuesta = inactivar(cliente, id_producto)
    assert respuesta.status_code == 200
    crudo = json.loads(respuesta.get_data(as_text=True))
    assert set(crudo) == CAMPOS
    assert crudo["estado"] == "INACTIVO"
    assert crudo["id_producto"] == id_producto
    for campo in ("precio_venta", "stock_minimo"):
        assert isinstance(crudo[campo], (int, float)) and not isinstance(crudo[campo], bool)
    assert (crudo["precio_venta"], crudo["stock_minimo"]) == (1500.5, 2.25)
    assert estado_producto(id_producto) == "INACTIVO"
    assert crudo == cliente.get(f"/productos/{id_producto}", headers=CABECERAS).get_json()


def test_inactivar_dos_veces_es_idempotente(cliente, categoria, contador_updates):
    id_producto = crear_producto("001", categoria)
    primera = inactivar(cliente, id_producto)
    segunda = inactivar(cliente, id_producto)
    assert primera.status_code == segunda.status_code == 200
    assert primera.get_json() == segunda.get_json()
    assert contador_updates == [(id_producto, "INACTIVO")]


def test_inactivar_en_categoria_inactiva(cliente, categoria):
    # Inactivar no depende de la categoría.
    id_producto = crear_producto("001", categoria)
    cambiar_estado_categoria(categoria, "INACTIVO")
    assert inactivar(cliente, id_producto).get_json()["estado"] == "INACTIVO"


# --- Activar ------------------------------------------------------------------


def test_activar_producto_inactivo(cliente, categoria):
    id_producto = crear_producto("001", categoria, estado="INACTIVO")
    respuesta = activar(cliente, id_producto)
    assert respuesta.status_code == 200
    assert set(respuesta.get_json()) == CAMPOS
    assert respuesta.get_json()["estado"] == "ACTIVO"
    assert estado_producto(id_producto) == "ACTIVO"


def test_activar_dos_veces_es_idempotente(cliente, categoria, contador_updates):
    id_producto = crear_producto("001", categoria, estado="INACTIVO")
    primera = activar(cliente, id_producto)
    segunda = activar(cliente, id_producto)
    assert primera.status_code == segunda.status_code == 200
    assert primera.get_json() == segunda.get_json()
    assert contador_updates == [(id_producto, "ACTIVO")]


def test_activar_con_categoria_inactiva_da_409(cliente, categoria, contador_updates):
    id_producto = crear_producto("001", categoria, estado="INACTIVO")
    cambiar_estado_categoria(categoria, "INACTIVO")
    error = verificar_error(activar(cliente, id_producto), 409, "CONFLICTO")
    assert error["mensaje"] == "La categoría del producto está inactiva."
    assert estado_producto(id_producto) == "INACTIVO"
    assert contador_updates == []


def test_activar_uno_ya_activo_en_categoria_inactiva_responde_sin_cambios(
        cliente, categoria, contador_updates):
    id_producto = crear_producto("001", categoria)
    cambiar_estado_categoria(categoria, "INACTIVO")
    respuesta = activar(cliente, id_producto)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["estado"] == "ACTIVO"
    assert contador_updates == []


# --- Errores comunes ----------------------------------------------------------


@pytest.mark.parametrize("accion", ["inactivar", "activar"])
def test_id_inexistente_da_404(cliente, accion):
    respuesta = cliente.post(f"/productos/999999999/{accion}", headers=CABECERAS)
    error = verificar_error(respuesta, 404, "NO_EXISTE")
    assert error["mensaje"] == "El producto no existe."


@pytest.mark.parametrize("accion", ["inactivar", "activar"])
@pytest.mark.parametrize("id_ruta", ["abc", "-1", "1.5"])
def test_id_no_entero_da_404(cliente, accion, id_ruta):
    respuesta = cliente.post(f"/productos/{id_ruta}/{accion}", headers=CABECERAS)
    verificar_error(respuesta, 404, "NO_EXISTE")


@pytest.mark.parametrize("accion", ["inactivar", "activar"])
def test_sin_token_da_401(cliente, categoria, accion):
    id_producto = crear_producto("001", categoria, estado="INACTIVO")
    verificar_error(cliente.post(f"/productos/{id_producto}/{accion}"), 401, "NO_AUTENTICADO")
    assert estado_producto(id_producto) == "INACTIVO"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"json": {"estado": "ACTIVO", "id_categoria": 1}},
        {"data": "no es json", "content_type": "text/plain"},
        {"data": "[1, 2]", "content_type": "application/json"},
    ],
)
def test_el_cuerpo_se_ignora(cliente, categoria, kwargs):
    id_producto = crear_producto("001", categoria)
    respuesta = inactivar(cliente, id_producto, **kwargs)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["estado"] == "INACTIVO"
    respuesta = activar(cliente, id_producto, **kwargs)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["estado"] == "ACTIVO"


@pytest.mark.parametrize("accion", ["inactivar", "activar"])
def test_get_no_permitido_da_405(cliente, accion):
    respuesta = cliente.get(f"/productos/1/{accion}", headers=CABECERAS)
    verificar_error(respuesta, 405, "METODO_NO_PERMITIDO")


# --- Reflejo en las consultas -------------------------------------------------


def test_consultas_reflejan_el_cambio(cliente, categoria):
    id_producto = crear_producto("001", categoria)
    crear_producto("002", categoria)
    inactivar(cliente, id_producto)

    inactivos = cliente.get(
        "/productos", headers=CABECERAS,
        query_string={"q": PREFIJO_SKU, "estado": "INACTIVO"}).get_json()
    assert [p["sku"] for p in inactivos["data"]] == [PREFIJO_SKU + "001"]

    por_sku = cliente.get(f"/productos/sku/{PREFIJO_SKU}001", headers=CABECERAS)
    assert por_sku.status_code == 200
    assert por_sku.get_json()["estado"] == "INACTIVO"


def test_inactivar_el_unico_activo_permite_inactivar_la_categoria(cliente, categoria):
    id_producto = crear_producto("001", categoria)
    crear_producto("002", categoria, estado="INACTIVO")

    respuesta = cliente.post(f"/categorias/{categoria}/inactivar", headers=CABECERAS)
    verificar_error(respuesta, 409, "CATEGORIA_CON_PRODUCTOS")

    inactivar(cliente, id_producto)
    respuesta = cliente.post(f"/categorias/{categoria}/inactivar", headers=CABECERAS)
    assert respuesta.status_code == 200
    assert estado_categoria(categoria) == "INACTIVO"


# --- Concurrencia ---------------------------------------------------------------


@pytest.mark.parametrize("ronda", range(10))
def test_concurrencia_inactivar_categoria_y_activar_producto(app, ronda):
    id_categoria = crear_categoria(f"concurrencia_{ronda}")
    id_producto = crear_producto(f"C{ronda}", id_categoria, estado="INACTIVO")
    barrera = threading.Barrier(2)
    resultados = {}

    def ejecutar(nombre, ruta):
        cliente = app.test_client()
        barrera.wait()
        resultados[nombre] = cliente.post(ruta, headers=CABECERAS).status_code

    hilos = [
        threading.Thread(target=ejecutar,
                         args=("categoria", f"/categorias/{id_categoria}/inactivar")),
        threading.Thread(target=ejecutar,
                         args=("producto", f"/productos/{id_producto}/activar")),
    ]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    # Gana una de las dos; la otra responde 409.
    assert sorted(resultados.values()) == [200, 409], resultados
    categoria_final = estado_categoria(id_categoria)
    producto_final = estado_producto(id_producto)
    assert not (categoria_final == "INACTIVO" and producto_final == "ACTIVO")
    if resultados["categoria"] == 200:
        assert (categoria_final, producto_final) == ("INACTIVO", "INACTIVO")
    else:
        assert (categoria_final, producto_final) == ("ACTIVO", "ACTIVO")
