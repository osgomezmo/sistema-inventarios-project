"""Pruebas de GET /productos, /productos/{id} y /productos/sku/{sku} contra el
MySQL de desarrollo.

Los productos de prueba llevan el prefijo de SKU PREFIJO_SKU y las categorías el
prefijo de nombre PREFIJO. Se insertan con SQL directo y un fixture borra al
terminar solo esas filas: primero productos, luego subcategorías y al final
raíces. Si MySQL no está disponible, las pruebas se saltan.
"""

import json

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
CAMPOS_SKU = {"sku", "nombre", "estado", "unidad_medida", "stock_minimo", "id_categoria"}
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


def crear_categoria(nombre, id_padre=None):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO categorias (nombre, id_categoria_padre) VALUES (%s, %s)",
            (PREFIJO + nombre, id_padre),
        )
        return cur.lastrowid


def crear_producto(sku, nombre, id_categoria, precio, stock_minimo="5.000",
                   estado="ACTIVO", unidad="UNIDAD", descripcion=None):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO productos (sku, nombre, descripcion, marca, id_categoria,"
            " unidad_medida, precio_venta, stock_minimo, estado)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (PREFIJO_SKU + sku, nombre, descripcion, "Marca de prueba", id_categoria,
             unidad, precio, stock_minimo, estado),
        )
        return cur.lastrowid


@pytest.fixture
def datos():
    """Raíz con una subcategoría, otra raíz y tres productos.

    Orden por nombre: A2 (Árbol), B1 (Detergente), A1 (Leche).
    """
    raiz = crear_categoria("raiz")
    sub = crear_categoria("raiz_sub", raiz)
    otra = crear_categoria("otra")
    ids = {
        "A1": crear_producto("A1", "zz Leche entera Alquería", sub, "1000.00", "12.500",
                             unidad="LITRO", descripcion="Bolsa de 1 L"),
        "A2": crear_producto("A2", "zz Árbol café", raiz, "2500.50"),
        "B1": crear_producto("B1", "zz Detergente 100% natural", otra, "5000.00",
                             estado="INACTIVO"),
    }
    return {"raiz": raiz, "sub": sub, "otra": otra, "ids": ids}


def get(cliente, ruta, **params):
    return cliente.get(ruta, headers=CABECERAS, query_string=params)


def listar(cliente, **params):
    respuesta = get(cliente, "/productos", **params)
    assert respuesta.status_code == 200, respuesta.get_json()
    return respuesta.get_json()


def skus(cuerpo):
    return [p["sku"].removeprefix(PREFIJO_SKU) for p in cuerpo["data"]]


def verificar_error(respuesta, status, codigo):
    assert respuesta.status_code == status
    error = respuesta.get_json()["error"]
    assert set(error) == {"codigo", "mensaje", "detalles"}
    assert error["codigo"] == codigo
    return error


# --- Listado ----------------------------------------------------------------


def test_listado_de_productos_de_prueba(cliente, datos):
    cuerpo = listar(cliente, q=PREFIJO_SKU)
    assert set(cuerpo) == {"data", "meta"}
    assert cuerpo["meta"] == {"page": 1, "per_page": 20, "total": 3}
    assert skus(cuerpo) == ["A2", "B1", "A1"]  # orden por nombre


def test_campos_exactos_y_numeros_json(cliente, datos):
    respuesta = get(cliente, "/productos", q=PREFIJO_SKU + "A1")
    crudo = json.loads(respuesta.get_data(as_text=True))
    producto = crudo["data"][0]
    assert set(producto) == CAMPOS
    for campo in ("precio_venta", "stock_minimo"):
        assert isinstance(producto[campo], (int, float))
        assert not isinstance(producto[campo], bool)
    assert producto["precio_venta"] == 1000
    assert producto["stock_minimo"] == 12.5
    assert producto["unidad_medida"] == "LITRO"
    assert producto["descripcion"] == "Bolsa de 1 L"
    assert producto["id_categoria"] == datos["sub"]
    assert producto["estado"] == "ACTIVO"


@pytest.mark.parametrize(
    "q, esperado",
    [
        ("ZZTEST-A1", ["A1"]),
        ("zztest-a", ["A2", "A1"]),
        ("Leche entera", ["A1"]),
        ("LECHE", ["A1"]),
        ("arbol cafe", ["A2"]),
        ("alqueria", ["A1"]),
    ],
)
def test_q_por_sku_y_nombre(cliente, datos, q, esperado):
    assert skus(listar(cliente, q=q, per_page=100)) == esperado


@pytest.mark.parametrize("q", ["ZZTEST-A_", "ZZTEST-A%", "ZZTEST\\A1"])
def test_comodines_de_q_valen_literales(cliente, datos, q):
    assert listar(cliente, q=q)["meta"]["total"] == 0


def test_q_con_porcentaje_literal(cliente, datos):
    assert skus(listar(cliente, q="100%")) == ["B1"]


@pytest.mark.parametrize("q", ["", "   "])
def test_q_vacio_se_ignora(cliente, datos, q):
    cuerpo = listar(cliente, q=q, per_page=100)
    assert cuerpo["meta"]["total"] >= 3


def test_filtro_estado(cliente, datos):
    assert skus(listar(cliente, q=PREFIJO_SKU, estado="INACTIVO")) == ["B1"]
    assert skus(listar(cliente, q=PREFIJO_SKU, estado="ACTIVO")) == ["A2", "A1"]


def test_id_categoria_raiz_incluye_subcategorias(cliente, datos):
    assert skus(listar(cliente, id_categoria=datos["raiz"])) == ["A2", "A1"]


def test_id_categoria_subcategoria_solo_los_suyos(cliente, datos):
    assert skus(listar(cliente, id_categoria=datos["sub"])) == ["A1"]
    assert skus(listar(cliente, id_categoria=datos["otra"])) == ["B1"]


def test_id_categoria_inexistente_da_lista_vacia(cliente, datos):
    cuerpo = listar(cliente, id_categoria=999_999_999)
    assert cuerpo == {"data": [], "meta": {"page": 1, "per_page": 20, "total": 0}}


@pytest.mark.parametrize(
    "params, esperado",
    [
        ({"precio_min": "1000"}, ["A2", "B1", "A1"]),
        ({"precio_min": "1000.01"}, ["A2", "B1"]),
        ({"precio_max": "2500.50"}, ["A2", "A1"]),
        ({"precio_max": "2500.49"}, ["A1"]),
        ({"precio_min": "1000", "precio_max": "2500.5"}, ["A2", "A1"]),
        ({"precio_min": "2500.50", "precio_max": "2500.50"}, ["A2"]),
        ({"precio_min": "0", "precio_max": "999.99"}, []),
    ],
)
def test_filtros_de_precio_inclusivos(cliente, datos, params, esperado):
    assert skus(listar(cliente, q=PREFIJO_SKU, **params)) == esperado


@pytest.mark.parametrize(
    "params, campo",
    [
        ({"precio_min": "3000", "precio_max": "2000"}, "precio_min"),
        ({"precio_min": "-1"}, "precio_min"),
        ({"precio_max": "-0.01"}, "precio_max"),
        ({"precio_min": "10.005"}, "precio_min"),
        ({"precio_min": "abc"}, "precio_min"),
        ({"precio_max": "nan"}, "precio_max"),
        ({"precio_max": "inf"}, "precio_max"),
        ({"id_categoria": "abc"}, "id_categoria"),
        ({"id_categoria": "1.5"}, "id_categoria"),
        ({"estado": "BORRADO"}, "estado"),
        ({"per_page": 101}, "per_page"),
        ({"page": 0}, "page"),
        ({"skus": ",".join(f"S{i}" for i in range(101))}, "skus"),
        ({"skus": "X" * 51}, "skus"),
    ],
)
def test_filtros_invalidos_dan_422(cliente, params, campo):
    error = verificar_error(get(cliente, "/productos", **params), 422, "VALIDACION")
    assert list(error["detalles"]) == [campo]


def test_varios_errores_se_reportan_juntos(cliente):
    respuesta = get(
        cliente, "/productos",
        id_categoria="x", estado="y", per_page=101, precio_min="abc", precio_max="-5",
        skus=",".join(["S"] * 101),
    )
    error = verificar_error(respuesta, 422, "VALIDACION")
    assert set(error["detalles"]) == {
        "id_categoria", "estado", "per_page", "precio_min", "precio_max", "skus"}


def test_skus_con_espacios_comas_e_inexistentes(cliente, datos):
    cuerpo = listar(cliente, skus=" ZZTEST-A1 , ,ZZTEST-NOEXISTE,zztest-b1,")
    assert skus(cuerpo) == ["B1", "A1"]
    assert cuerpo["meta"]["total"] == 2


def test_skus_exactamente_100_se_acepta(cliente, datos):
    lista = ["ZZTEST-A1"] + [f"ZZTEST-N{i}" for i in range(99)]
    assert skus(listar(cliente, skus=",".join(lista))) == ["A1"]


@pytest.mark.parametrize("valor", ["", " , ,"])
def test_skus_vacio_da_lista_vacia(cliente, datos, valor):
    assert listar(cliente, skus=valor) == {
        "data": [], "meta": {"page": 1, "per_page": 20, "total": 0}}


def test_skus_combinado_con_q(cliente, datos):
    cuerpo = listar(cliente, skus="ZZTEST-A1,ZZTEST-B1", q="detergente")
    assert skus(cuerpo) == ["B1"]


def test_filtros_combinados_con_and(cliente, datos):
    cuerpo = listar(cliente, id_categoria=datos["raiz"], precio_max="1500", estado="ACTIVO")
    assert skus(cuerpo) == ["A1"]


def test_paginacion(cliente, datos):
    primera = listar(cliente, q=PREFIJO_SKU, per_page=2)
    assert primera["meta"] == {"page": 1, "per_page": 2, "total": 3}
    assert skus(primera) == ["A2", "B1"]

    segunda = listar(cliente, q=PREFIJO_SKU, per_page=2, page=2)
    assert segunda["meta"] == {"page": 2, "per_page": 2, "total": 3}
    assert skus(segunda) == ["A1"]

    fuera = listar(cliente, q=PREFIJO_SKU, per_page=2, page=5)
    assert fuera["data"] == [] and fuera["meta"]["total"] == 3


# --- Por id -------------------------------------------------------------------


def test_obtener_por_id(cliente, datos):
    respuesta = get(cliente, f"/productos/{datos['ids']['A2']}")
    assert respuesta.status_code == 200
    producto = respuesta.get_json()
    assert set(producto) == CAMPOS
    assert producto["sku"] == PREFIJO_SKU + "A2"
    assert producto["precio_venta"] == 2500.5
    assert producto["descripcion"] is None


def test_obtener_por_id_inexistente_da_404(cliente):
    error = verificar_error(get(cliente, "/productos/999999999"), 404, "NO_EXISTE")
    assert error["mensaje"] == "El producto no existe."


@pytest.mark.parametrize("ruta", ["/productos/abc", "/productos/-1", "/productos/1.5"])
def test_id_no_entero_da_404(cliente, ruta):
    verificar_error(get(cliente, ruta), 404, "NO_EXISTE")


# --- Por SKU ------------------------------------------------------------------


def test_obtener_por_sku_solo_campos_del_contrato(cliente, datos):
    respuesta = get(cliente, "/productos/sku/ZZTEST-A1")
    assert respuesta.status_code == 200
    producto = respuesta.get_json()
    assert set(producto) == CAMPOS_SKU
    assert producto == {
        "sku": "ZZTEST-A1",
        "nombre": "zz Leche entera Alquería",
        "estado": "ACTIVO",
        "unidad_medida": "LITRO",
        "stock_minimo": 12.5,
        "id_categoria": datos["sub"],
    }


def test_obtener_por_sku_inactivo(cliente, datos):
    producto = get(cliente, "/productos/sku/ZZTEST-B1").get_json()
    assert producto["estado"] == "INACTIVO"


def test_obtener_por_sku_en_minusculas(cliente, datos):
    respuesta = get(cliente, "/productos/sku/zztest-a2")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["sku"] == "ZZTEST-A2"


def test_obtener_por_sku_inexistente_da_404(cliente):
    error = verificar_error(get(cliente, "/productos/sku/ZZTEST-NOEXISTE"), 404, "NO_EXISTE")
    assert error["mensaje"] == "El producto no existe."


# --- Autenticación ------------------------------------------------------------


@pytest.mark.parametrize("ruta", ["/productos", "/productos/1", "/productos/sku/ZZTEST-A1"])
def test_sin_token_da_401(cliente, ruta):
    verificar_error(cliente.get(ruta), 401, "NO_AUTENTICADO")
