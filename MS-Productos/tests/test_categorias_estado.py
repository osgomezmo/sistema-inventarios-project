"""Pruebas de POST /categorias/{id}/inactivar y /activar contra el MySQL de desarrollo.

Las categorías de prueba llevan el prefijo de nombre PREFIJO y los productos el
prefijo de SKU PREFIJO_SKU. Un fixture borra al terminar solo esas filas:
primero productos, luego subcategorías y al final raíces. Si MySQL no está
disponible, las pruebas se saltan.
"""

import pytest

from app import create_app
from app.config import cargar_configuracion
from app.db import abrir_conexion, transaccion
from app.errors import ApiError

PREFIJO = "zz_test_"
PREFIJO_SKU = "ZZTEST-"
TOKEN = "token-de-prueba"
CABECERAS = {"Authorization": f"Bearer {TOKEN}"}
CAMPOS = {"id_categoria", "nombre", "descripcion", "id_categoria_padre", "estado"}
CAMPOS_RAIZ = CAMPOS | {"subcategorias"}
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
def cliente():
    return create_app({"TESTING": True, "SERVICE_TOKEN": TOKEN}).test_client()


def crear_categoria(nombre, id_padre=None, estado="ACTIVO"):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO categorias (nombre, id_categoria_padre, estado) VALUES (%s, %s, %s)",
            (PREFIJO + nombre, id_padre, estado),
        )
        return cur.lastrowid


def crear_producto(sku, id_categoria, estado="ACTIVO"):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO productos (sku, nombre, marca, id_categoria, unidad_medida,"
            " precio_venta, stock_minimo, estado) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (PREFIJO_SKU + sku, "Producto de prueba", "Marca", id_categoria, "UNIDAD",
             "1000.00", "5.000", estado),
        )
        return cur.lastrowid


def estados(*ids):
    with transaccion(CONFIG) as cur:
        cur.execute(
            f"SELECT id_categoria, estado FROM categorias"
            f" WHERE id_categoria IN ({', '.join(['%s'] * len(ids))})",
            ids,
        )
        por_id = {f["id_categoria"]: f["estado"] for f in cur.fetchall()}
    return [por_id[i] for i in ids]


def inactivar(cliente, id_categoria, **kwargs):
    return cliente.post(f"/categorias/{id_categoria}/inactivar", headers=CABECERAS, **kwargs)


def activar(cliente, id_categoria, **kwargs):
    return cliente.post(f"/categorias/{id_categoria}/activar", headers=CABECERAS, **kwargs)


def obtener(cliente, id_categoria):
    return cliente.get(f"/categorias/{id_categoria}", headers=CABECERAS).get_json()


def verificar_error(respuesta, status, codigo):
    assert respuesta.status_code == status
    error = respuesta.get_json()["error"]
    assert set(error) == {"codigo", "mensaje", "detalles"}
    assert error["codigo"] == codigo
    return error


@pytest.fixture
def raiz_con_hijas():
    id_raiz = crear_categoria("raiz")
    id_a = crear_categoria("raiz_a", id_raiz)
    id_b = crear_categoria("raiz_b", id_raiz)
    return id_raiz, id_a, id_b


# --- Inactivar ----------------------------------------------------------------


def test_inactivar_subcategoria(cliente, raiz_con_hijas):
    id_raiz, id_a, id_b = raiz_con_hijas
    respuesta = inactivar(cliente, id_a)
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert set(cuerpo) == CAMPOS
    assert cuerpo["estado"] == "INACTIVO"
    assert estados(id_raiz, id_a, id_b) == ["ACTIVO", "INACTIVO", "ACTIVO"]


def test_inactivar_raiz_inactiva_sus_subcategorias(cliente, raiz_con_hijas):
    id_raiz, id_a, id_b = raiz_con_hijas
    respuesta = inactivar(cliente, id_raiz)
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert set(cuerpo) == CAMPOS_RAIZ
    assert cuerpo["estado"] == "INACTIVO"
    assert [s["estado"] for s in cuerpo["subcategorias"]] == ["INACTIVO", "INACTIVO"]

    consultada = obtener(cliente, id_raiz)
    assert consultada["estado"] == "INACTIVO"
    assert {s["id_categoria"]: s["estado"] for s in consultada["subcategorias"]} == {
        id_a: "INACTIVO", id_b: "INACTIVO"}


def test_producto_activo_en_la_raiz_bloquea(cliente, raiz_con_hijas):
    id_raiz, id_a, id_b = raiz_con_hijas
    crear_producto("RAIZ", id_raiz)
    error = verificar_error(inactivar(cliente, id_raiz), 409, "CATEGORIA_CON_PRODUCTOS")
    assert error["mensaje"]
    assert estados(id_raiz, id_a, id_b) == ["ACTIVO"] * 3


def test_producto_activo_en_una_subcategoria_bloquea_la_raiz(cliente, raiz_con_hijas):
    id_raiz, id_a, id_b = raiz_con_hijas
    crear_producto("SUB-B", id_b)
    verificar_error(inactivar(cliente, id_raiz), 409, "CATEGORIA_CON_PRODUCTOS")
    assert estados(id_raiz, id_a, id_b) == ["ACTIVO"] * 3


def test_subcategoria_solo_revisa_sus_productos(cliente, raiz_con_hijas):
    id_raiz, id_a, id_b = raiz_con_hijas
    crear_producto("SUB-B", id_b)
    crear_producto("RAIZ", id_raiz)
    # La hermana y la raíz tienen productos, pero la subcategoría a no.
    assert inactivar(cliente, id_a).status_code == 200
    verificar_error(inactivar(cliente, id_b), 409, "CATEGORIA_CON_PRODUCTOS")
    assert estados(id_raiz, id_a, id_b) == ["ACTIVO", "INACTIVO", "ACTIVO"]


def test_producto_inactivo_no_bloquea(cliente, raiz_con_hijas):
    id_raiz, id_a, _ = raiz_con_hijas
    crear_producto("INACTIVO-RAIZ", id_raiz, estado="INACTIVO")
    crear_producto("INACTIVO-SUB", id_a, estado="INACTIVO")
    assert inactivar(cliente, id_raiz).status_code == 200


def test_inactivar_dos_veces_es_idempotente(cliente, raiz_con_hijas):
    id_raiz, _, _ = raiz_con_hijas
    primera = inactivar(cliente, id_raiz)
    segunda = inactivar(cliente, id_raiz)
    assert primera.status_code == segunda.status_code == 200
    assert primera.get_json() == segunda.get_json()


def test_inactivar_ignora_el_cuerpo(cliente):
    id_raiz = crear_categoria("con_cuerpo")
    respuesta = inactivar(cliente, id_raiz, json={"estado": "ACTIVO", "x": 1})
    assert respuesta.status_code == 200
    assert respuesta.get_json()["estado"] == "INACTIVO"


# --- Activar ------------------------------------------------------------------


def test_activar_subcategoria_con_raiz_inactiva_da_409(cliente, raiz_con_hijas):
    id_raiz, id_a, _ = raiz_con_hijas
    inactivar(cliente, id_raiz)
    error = verificar_error(activar(cliente, id_a), 409, "CONFLICTO")
    assert "raíz" in error["mensaje"]
    assert estados(id_a) == ["INACTIVO"]


def test_activar_raiz_no_reactiva_subcategorias(cliente, raiz_con_hijas):
    id_raiz, id_a, id_b = raiz_con_hijas
    inactivar(cliente, id_raiz)
    respuesta = activar(cliente, id_raiz)
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert set(cuerpo) == CAMPOS_RAIZ
    assert cuerpo["estado"] == "ACTIVO"
    assert [s["estado"] for s in cuerpo["subcategorias"]] == ["INACTIVO", "INACTIVO"]
    assert estados(id_raiz, id_a, id_b) == ["ACTIVO", "INACTIVO", "INACTIVO"]


def test_activar_subcategoria_con_raiz_activa(cliente, raiz_con_hijas):
    id_raiz, id_a, id_b = raiz_con_hijas
    inactivar(cliente, id_raiz)
    activar(cliente, id_raiz)
    respuesta = activar(cliente, id_a)
    assert respuesta.status_code == 200
    assert set(respuesta.get_json()) == CAMPOS
    assert respuesta.get_json()["estado"] == "ACTIVO"
    assert estados(id_raiz, id_a, id_b) == ["ACTIVO", "ACTIVO", "INACTIVO"]


def test_activar_dos_veces_es_idempotente(cliente):
    id_raiz = crear_categoria("dos_veces", estado="INACTIVO")
    primera = activar(cliente, id_raiz)
    segunda = activar(cliente, id_raiz)
    assert primera.status_code == segunda.status_code == 200
    assert primera.get_json() == segunda.get_json()
    assert primera.get_json()["estado"] == "ACTIVO"


def test_activar_una_activa_responde_sin_cambios(cliente, raiz_con_hijas):
    _, id_a, _ = raiz_con_hijas
    respuesta = activar(cliente, id_a)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["estado"] == "ACTIVO"


# --- Errores comunes ----------------------------------------------------------


@pytest.mark.parametrize("accion", ["inactivar", "activar"])
def test_id_inexistente_da_404(cliente, accion):
    respuesta = cliente.post(f"/categorias/999999999/{accion}", headers=CABECERAS)
    error = verificar_error(respuesta, 404, "NO_EXISTE")
    assert error["mensaje"] == "La categoría no existe."


@pytest.mark.parametrize("accion", ["inactivar", "activar"])
@pytest.mark.parametrize("id_ruta", ["abc", "-1", "1.5"])
def test_id_no_entero_da_404(cliente, accion, id_ruta):
    respuesta = cliente.post(f"/categorias/{id_ruta}/{accion}", headers=CABECERAS)
    verificar_error(respuesta, 404, "NO_EXISTE")


@pytest.mark.parametrize("accion", ["inactivar", "activar"])
def test_sin_token_da_401(cliente, accion):
    verificar_error(cliente.post(f"/categorias/1/{accion}"), 401, "NO_AUTENTICADO")


@pytest.mark.parametrize("accion", ["inactivar", "activar"])
def test_get_no_permitido_da_405(cliente, accion):
    respuesta = cliente.get(f"/categorias/1/{accion}", headers=CABECERAS)
    verificar_error(respuesta, 405, "METODO_NO_PERMITIDO")


# --- Reflejo en el listado ----------------------------------------------------


def ids_propios(cliente, **params):
    """Ids de las raíces de prueba en el listado, recorriendo todas las páginas."""
    encontrados, page = {}, 1
    while True:
        cuerpo = cliente.get(
            "/categorias", headers=CABECERAS,
            query_string={"page": page, "per_page": 100, **params},
        ).get_json()
        for raiz in cuerpo["data"]:
            if raiz["nombre"].startswith(PREFIJO):
                encontrados[raiz["id_categoria"]] = [
                    s["id_categoria"] for s in raiz["subcategorias"]]
        if page * 100 >= cuerpo["meta"]["total"]:
            return encontrados
        page += 1


def test_filtro_estado_refleja_los_cambios(cliente, raiz_con_hijas):
    id_raiz, id_a, id_b = raiz_con_hijas
    id_otra = crear_categoria("otra")

    inactivar(cliente, id_raiz)
    assert ids_propios(cliente, estado="ACTIVO") == {id_otra: []}
    assert ids_propios(cliente, estado="INACTIVO") == {id_raiz: [id_a, id_b]}

    activar(cliente, id_raiz)
    activar(cliente, id_a)
    assert ids_propios(cliente, estado="ACTIVO") == {id_raiz: [id_a], id_otra: []}
    assert ids_propios(cliente, estado="INACTIVO") == {}
