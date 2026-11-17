"""Pruebas de PUT /productos/{id} contra el MySQL de desarrollo.

Los productos de prueba llevan el prefijo de SKU PREFIJO_SKU y las categorías el
prefijo de nombre PREFIJO. Un fixture borra al terminar solo esas filas:
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
CAMPOS = {
    "id_producto", "sku", "nombre", "descripcion", "marca", "id_categoria",
    "unidad_medida", "precio_venta", "stock_minimo", "estado",
}
CONFIG = cargar_configuracion()
QUITAR = object()


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


def crear_producto(id_categoria, unidad="KILO", estado="ACTIVO"):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO productos (sku, nombre, descripcion, marca, id_categoria,"
            " unidad_medida, precio_venta, stock_minimo, estado)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (PREFIJO_SKU + "001", "Arroz", "Bolsa de 1 kg", "Marca A", id_categoria,
             unidad, "3000.00", "2.500", estado),
        )
        return cur.lastrowid


def leer_sql(id_producto):
    with transaccion(CONFIG) as cur:
        cur.execute("SELECT * FROM productos WHERE id_producto = %s", (id_producto,))
        return cur.fetchone()


@pytest.fixture
def categoria():
    return crear_categoria("raiz")


@pytest.fixture
def producto(categoria):
    return crear_producto(categoria)


def cuerpo_valido(categoria_destino, **cambios):
    cuerpo = {
        "nombre": "Arroz premium",
        "descripcion": "Bolsa de 500 g",
        "marca": "Marca B",
        "id_categoria": categoria_destino,
        "unidad_medida": "LITRO",
        "precio_venta": "3500.75",
        "stock_minimo": 1.125,
    }
    cuerpo.update(cambios)
    return {k: v for k, v in cuerpo.items() if v is not QUITAR}


def put(cliente, id_producto, cuerpo):
    return cliente.put(f"/productos/{id_producto}", headers=CABECERAS, json=cuerpo)


def verificar_error(respuesta, status, codigo):
    assert respuesta.status_code == status, respuesta.get_json()
    error = respuesta.get_json()["error"]
    assert set(error) == {"codigo", "mensaje", "detalles"}
    assert error["codigo"] == codigo
    return error


def verificar_422(respuesta, *campos):
    error = verificar_error(respuesta, 422, "VALIDACION")
    assert set(error["detalles"]) == set(campos)
    return error


# --- Edición válida -----------------------------------------------------------


def test_cambia_todos_los_campos_editables(cliente, categoria, producto):
    respuesta = put(cliente, producto, cuerpo_valido(categoria))
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert set(cuerpo) == CAMPOS
    assert cuerpo == {
        "id_producto": producto,
        "sku": PREFIJO_SKU + "001",
        "nombre": "Arroz premium",
        "descripcion": "Bolsa de 500 g",
        "marca": "Marca B",
        "id_categoria": categoria,
        "unidad_medida": "LITRO",
        "precio_venta": 3500.75,
        "stock_minimo": 1.125,
        "estado": "ACTIVO",
    }
    otra = cliente.get(f"/productos/{producto}", headers=CABECERAS)
    assert otra.get_json() == cuerpo


@pytest.mark.parametrize("descripcion", [QUITAR, None])
def test_descripcion_ausente_o_null_queda_null(cliente, categoria, producto, descripcion):
    cuerpo = put(cliente, producto, cuerpo_valido(categoria, descripcion=descripcion)).get_json()
    assert cuerpo["descripcion"] is None
    assert leer_sql(producto)["descripcion"] is None


def test_sku_del_cuerpo_se_ignora(cliente, categoria, producto):
    respuesta = put(cliente, producto, cuerpo_valido(categoria, sku="ZZTEST-OTRO"))
    assert respuesta.status_code == 200
    assert respuesta.get_json()["sku"] == PREFIJO_SKU + "001"
    assert leer_sql(producto)["sku"] == PREFIJO_SKU + "001"


def test_sku_invalido_en_el_cuerpo_tambien_se_ignora(cliente, categoria, producto):
    assert put(cliente, producto, cuerpo_valido(categoria, sku="MAL SKU /")).status_code == 200


def test_estado_del_cuerpo_se_ignora(cliente, categoria, producto):
    cuerpo = put(cliente, producto, cuerpo_valido(categoria, estado="INACTIVO")).get_json()
    assert cuerpo["estado"] == "ACTIVO"
    assert leer_sql(producto)["estado"] == "ACTIVO"


def test_producto_inactivo_se_edita_y_sigue_inactivo(cliente, categoria):
    id_producto = crear_producto(categoria, estado="INACTIVO")
    cuerpo = put(cliente, id_producto, cuerpo_valido(categoria, estado="ACTIVO")).get_json()
    assert cuerpo["nombre"] == "Arroz premium"
    assert cuerpo["estado"] == "INACTIVO"


def test_mover_a_otra_categoria_activa(cliente, categoria, producto):
    sub = crear_categoria("sub", categoria)
    respuesta = put(cliente, producto, cuerpo_valido(sub))
    assert respuesta.status_code == 200
    assert respuesta.get_json()["id_categoria"] == sub


def test_mover_a_categoria_inactiva_da_422(cliente, categoria, producto):
    inactiva = crear_categoria("inactiva", estado="INACTIVO")
    error = verificar_422(put(cliente, producto, cuerpo_valido(inactiva)), "id_categoria")
    assert error["detalles"]["id_categoria"] == ["La categoría está inactiva."]
    assert leer_sql(producto)["id_categoria"] == categoria


def test_mover_a_categoria_inexistente_da_422(cliente, categoria, producto):
    error = verificar_422(put(cliente, producto, cuerpo_valido(999_999_999)), "id_categoria")
    assert error["detalles"]["id_categoria"] == ["La categoría no existe."]


def test_de_kilo_a_unidad_con_stock_decimal_da_422(cliente, categoria, producto):
    cuerpo = cuerpo_valido(categoria, unidad_medida="UNIDAD", stock_minimo="2.5")
    verificar_422(put(cliente, producto, cuerpo), "stock_minimo")
    assert leer_sql(producto)["unidad_medida"] == "KILO"


def test_de_kilo_a_unidad_con_stock_entero(cliente, categoria, producto):
    cuerpo = put(
        cliente, producto, cuerpo_valido(categoria, unidad_medida="UNIDAD", stock_minimo=3)
    ).get_json()
    assert (cuerpo["unidad_medida"], cuerpo["stock_minimo"]) == ("UNIDAD", 3)


# --- Errores ------------------------------------------------------------------


def test_id_inexistente_da_404(cliente, categoria):
    error = verificar_error(put(cliente, 999_999_999, cuerpo_valido(categoria)), 404, "NO_EXISTE")
    assert error["mensaje"] == "El producto no existe."


@pytest.mark.parametrize("ruta", ["/productos/abc", "/productos/-1", "/productos/1.5"])
def test_id_no_entero_da_404(cliente, categoria, ruta):
    respuesta = cliente.put(ruta, headers=CABECERAS, json=cuerpo_valido(categoria))
    verificar_error(respuesta, 404, "NO_EXISTE")


def test_cuerpo_invalido_con_id_inexistente_da_422(cliente):
    verificar_422(put(cliente, 999_999_999, {"nombre": ""}),
                  "nombre", "marca", "id_categoria", "unidad_medida",
                  "precio_venta", "stock_minimo")


def test_id_inexistente_con_categoria_inexistente_da_404(cliente):
    verificar_error(put(cliente, 999_999_999, cuerpo_valido(999_999_999)), 404, "NO_EXISTE")


@pytest.mark.parametrize(
    "cambios, campo",
    [
        ({"nombre": QUITAR}, "nombre"),
        ({"marca": "x" * 101}, "marca"),
        ({"descripcion": "x" * 1001}, "descripcion"),
        ({"id_categoria": "abc"}, "id_categoria"),
        ({"unidad_medida": "kilo"}, "unidad_medida"),
        ({"precio_venta": 1.005}, "precio_venta"),
        ({"stock_minimo": -1}, "stock_minimo"),
    ],
)
def test_campos_invalidos_dan_422(cliente, categoria, producto, cambios, campo):
    verificar_422(put(cliente, producto, cuerpo_valido(categoria, **cambios)), campo)
    assert leer_sql(producto)["nombre"] == "Arroz"


def test_errores_de_campos_juntos(cliente, categoria, producto):
    cuerpo = cuerpo_valido(
        categoria, nombre="", marca=None, precio_venta="abc", unidad_medida="CAJA")
    verificar_422(put(cliente, producto, cuerpo),
                  "nombre", "marca", "precio_venta", "unidad_medida")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"data": "nombre=x", "content_type": "application/x-www-form-urlencoded"},
        {"data": "[1]", "content_type": "application/json"},
        {"data": "texto", "content_type": "text/plain"},
    ],
)
def test_cuerpo_no_json_da_400(cliente, producto, kwargs):
    respuesta = cliente.put(f"/productos/{producto}", headers=CABECERAS, **kwargs)
    verificar_error(respuesta, 400, "PETICION_INVALIDA")


def test_sin_token_da_401(cliente, categoria, producto):
    respuesta = cliente.put(f"/productos/{producto}", json=cuerpo_valido(categoria))
    verificar_error(respuesta, 401, "NO_AUTENTICADO")
    assert leer_sql(producto)["nombre"] == "Arroz"
