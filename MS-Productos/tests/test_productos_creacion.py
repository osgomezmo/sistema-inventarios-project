"""Pruebas de POST /productos contra el MySQL de desarrollo.

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


def crear_categoria(nombre, id_padre=None, estado="ACTIVO"):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO categorias (nombre, id_categoria_padre, estado) VALUES (%s, %s, %s)",
            (PREFIJO + nombre, id_padre, estado),
        )
        return cur.lastrowid


@pytest.fixture
def categoria():
    return crear_categoria("raiz")


def cuerpo_valido(id_categoria, **cambios):
    cuerpo = {
        "sku": PREFIJO_SKU + "001",
        "nombre": "Leche entera 1 L",
        "descripcion": "Bolsa",
        "marca": "Alquería",
        "id_categoria": id_categoria,
        "unidad_medida": "UNIDAD",
        "precio_venta": 4250.5,
        "stock_minimo": 12,
    }
    cuerpo.update(cambios)
    return {k: v for k, v in cuerpo.items() if v is not QUITAR}


QUITAR = object()


def post(cliente, cuerpo, **kwargs):
    return cliente.post("/productos", headers=CABECERAS, json=cuerpo, **kwargs)


def filas_con_sku(sku):
    with transaccion(CONFIG) as cur:
        cur.execute("SELECT * FROM productos WHERE sku = %s", (sku,))
        return cur.fetchall()


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


# --- Creación válida --------------------------------------------------------


def test_crea_producto(cliente, categoria):
    respuesta = post(cliente, cuerpo_valido(categoria))
    assert respuesta.status_code == 201
    crudo = json.loads(respuesta.get_data(as_text=True))
    assert set(crudo) == CAMPOS
    assert crudo["sku"] == PREFIJO_SKU + "001"
    assert crudo["nombre"] == "Leche entera 1 L"
    assert crudo["descripcion"] == "Bolsa"
    assert crudo["marca"] == "Alquería"
    assert crudo["id_categoria"] == categoria
    assert crudo["unidad_medida"] == "UNIDAD"
    assert crudo["estado"] == "ACTIVO"
    for campo in ("precio_venta", "stock_minimo"):
        assert isinstance(crudo[campo], (int, float)) and not isinstance(crudo[campo], bool)
    assert crudo["precio_venta"] == 4250.5
    assert crudo["stock_minimo"] == 12

    # Lo devuelto coincide con GET /productos/{id}.
    otra = cliente.get(f"/productos/{crudo['id_producto']}", headers=CABECERAS)
    assert otra.get_json() == crudo


def test_crea_en_subcategoria(cliente, categoria):
    sub = crear_categoria("sub", categoria)
    respuesta = post(cliente, cuerpo_valido(sub))
    assert respuesta.status_code == 201
    assert respuesta.get_json()["id_categoria"] == sub


def test_sku_se_recorta_y_pasa_a_mayusculas(cliente, categoria):
    respuesta = post(cliente, cuerpo_valido(categoria, sku="zztest-abc "))
    assert respuesta.get_json()["sku"] == "ZZTEST-ABC"
    assert len(filas_con_sku("ZZTEST-ABC")) == 1


@pytest.mark.parametrize("repetido", ["ZZTEST-001", "zztest-001", " ZzTeSt-001 "])
def test_sku_duplicado_da_409(cliente, categoria, repetido):
    assert post(cliente, cuerpo_valido(categoria)).status_code == 201
    error = verificar_error(
        post(cliente, cuerpo_valido(categoria, sku=repetido, nombre="Otro")),
        409, "SKU_DUPLICADO")
    assert list(error["detalles"]) == ["sku"]
    # Atomicidad: sigue habiendo una sola fila, la original.
    filas = filas_con_sku("ZZTEST-001")
    assert len(filas) == 1 and filas[0]["nombre"] == "Leche entera 1 L"


def test_sku_de_50_caracteres_se_acepta(cliente, categoria):
    sku = PREFIJO_SKU + "X" * (50 - len(PREFIJO_SKU))
    assert post(cliente, cuerpo_valido(categoria, sku=sku)).status_code == 201


@pytest.mark.parametrize(
    "sku",
    [QUITAR, None, "", "   ", PREFIJO_SKU + "X" * 44, "ZZTEST-A B", "ZZTEST-A/B", "ZZTEST-Ñ", 123],
)
def test_sku_invalido_da_422(cliente, categoria, sku):
    verificar_422(post(cliente, cuerpo_valido(categoria, sku=sku)), "sku")


def test_concurrencia_mismo_sku(app, categoria):
    barrera = threading.Barrier(2)
    resultados = []

    def crear():
        cliente = app.test_client()
        barrera.wait()
        resultados.append(post(cliente, cuerpo_valido(categoria)).status_code)

    hilos = [threading.Thread(target=crear) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert sorted(resultados) == [201, 409]
    assert len(filas_con_sku("ZZTEST-001")) == 1


# --- Textos -------------------------------------------------------------------


def test_texto_con_tildes_enie_y_comilla(cliente, categoria):
    texto = PREFIJO + "O'Brien ñandú"
    cuerpo = post(
        cliente, cuerpo_valido(categoria, nombre=texto, marca=texto, descripcion=texto)
    ).get_json()
    assert cuerpo["nombre"] == cuerpo["marca"] == cuerpo["descripcion"] == texto


def test_textos_se_recortan(cliente, categoria):
    cuerpo = post(
        cliente, cuerpo_valido(categoria, nombre="  Leche  ", marca=" Marca ", descripcion=" D ")
    ).get_json()
    assert (cuerpo["nombre"], cuerpo["marca"], cuerpo["descripcion"]) == ("Leche", "Marca", "D")


@pytest.mark.parametrize(
    "campo, largo_ok",
    [("nombre", 150), ("marca", 100), ("descripcion", 1000)],
)
def test_limites_de_texto(cliente, categoria, campo, largo_ok):
    respuesta = post(cliente, cuerpo_valido(categoria, **{campo: "x" * largo_ok}))
    assert respuesta.status_code == 201
    verificar_422(
        post(cliente, cuerpo_valido(categoria, sku="ZZTEST-002", **{campo: "x" * (largo_ok + 1)})),
        campo)


@pytest.mark.parametrize("descripcion", [QUITAR, None, "", "   "])
def test_descripcion_ausente_o_null_queda_null(cliente, categoria, descripcion):
    respuesta = post(cliente, cuerpo_valido(categoria, descripcion=descripcion))
    assert respuesta.status_code == 201
    assert respuesta.get_json()["descripcion"] is None


@pytest.mark.parametrize("campo", ["nombre", "marca"])
@pytest.mark.parametrize("valor", [QUITAR, None, "", "  ", 5])
def test_nombre_y_marca_obligatorios(cliente, categoria, campo, valor):
    verificar_422(post(cliente, cuerpo_valido(categoria, **{campo: valor})), campo)


# --- Unidad de medida ---------------------------------------------------------


@pytest.mark.parametrize("unidad", ["UNIDAD", "KILO", "LITRO"])
def test_unidades_validas(cliente, categoria, unidad):
    respuesta = post(cliente, cuerpo_valido(categoria, unidad_medida=unidad))
    assert respuesta.status_code == 201
    assert respuesta.get_json()["unidad_medida"] == unidad


@pytest.mark.parametrize("unidad", [QUITAR, None, "", "kilo", "Kilo", "GRAMO", 1])
def test_unidad_invalida_da_422(cliente, categoria, unidad):
    verificar_422(post(cliente, cuerpo_valido(categoria, unidad_medida=unidad)), "unidad_medida")


# --- Números ------------------------------------------------------------------


@pytest.mark.parametrize(
    "precio, esperado",
    [(0, 0), (12.34, 12.34), ("12.50", 12.5), (999999999999.99, 999999999999.99), (7, 7)],
)
def test_precio_valido(cliente, categoria, precio, esperado):
    respuesta = post(cliente, cuerpo_valido(categoria, precio_venta=precio))
    assert respuesta.status_code == 201
    assert respuesta.get_json()["precio_venta"] == esperado


@pytest.mark.parametrize(
    "precio",
    [QUITAR, None, -1, -0.01, 12.345, "abc", True, "nan", "inf", "1e3", 1000000000000, ""],
)
def test_precio_invalido_da_422(cliente, categoria, precio):
    verificar_422(post(cliente, cuerpo_valido(categoria, precio_venta=precio)), "precio_venta")


@pytest.mark.parametrize("unidad", ["KILO", "LITRO"])
def test_stock_con_tres_decimales_en_kilo_y_litro(cliente, categoria, unidad):
    respuesta = post(cliente, cuerpo_valido(categoria, unidad_medida=unidad, stock_minimo="2.125"))
    assert respuesta.status_code == 201
    assert respuesta.get_json()["stock_minimo"] == 2.125


@pytest.mark.parametrize("stock, esperado", [(5, 5), ("5", 5), (5.0, 5), (0, 0)])
def test_stock_entero_con_unidad(cliente, categoria, stock, esperado):
    respuesta = post(cliente, cuerpo_valido(categoria, unidad_medida="UNIDAD", stock_minimo=stock))
    assert respuesta.status_code == 201
    assert respuesta.get_json()["stock_minimo"] == esperado


@pytest.mark.parametrize("stock", [2.5, "0.001"])
def test_stock_decimal_con_unidad_da_422(cliente, categoria, stock):
    error = verificar_422(
        post(cliente, cuerpo_valido(categoria, unidad_medida="UNIDAD", stock_minimo=stock)),
        "stock_minimo")
    assert "entero" in error["detalles"]["stock_minimo"][0]


@pytest.mark.parametrize(
    "stock", [QUITAR, None, -1, "1.2345", 100000000000, True, "abc", "nan"])
def test_stock_invalido_da_422(cliente, categoria, stock):
    verificar_422(
        post(cliente, cuerpo_valido(categoria, unidad_medida="KILO", stock_minimo=stock)),
        "stock_minimo")


# --- Categoría ----------------------------------------------------------------


@pytest.mark.parametrize("valor", [QUITAR, None, "", "abc", 1.5, True, 0])
def test_id_categoria_invalido_da_422(cliente, valor):
    verificar_422(post(cliente, cuerpo_valido(valor)), "id_categoria")


def test_categoria_inexistente_da_422(cliente):
    error = verificar_422(post(cliente, cuerpo_valido(999_999_999)), "id_categoria")
    assert error["detalles"]["id_categoria"] == ["La categoría no existe."]


def test_categoria_inactiva_da_422(cliente):
    inactiva = crear_categoria("inactiva", estado="INACTIVO")
    error = verificar_422(post(cliente, cuerpo_valido(inactiva)), "id_categoria")
    assert error["detalles"]["id_categoria"] == ["La categoría está inactiva."]
    assert filas_con_sku("ZZTEST-001") == []


def test_id_categoria_como_texto_numerico(cliente, categoria):
    respuesta = post(cliente, cuerpo_valido(str(categoria)))
    assert respuesta.status_code == 201
    assert respuesta.get_json()["id_categoria"] == categoria


# --- Varios errores y cuerpo ----------------------------------------------------


def test_varios_errores_juntos(cliente, categoria):
    cuerpo = cuerpo_valido(
        categoria, sku="MAL SKU", nombre="", precio_venta=-1, unidad_medida="caja")
    verificar_422(post(cliente, cuerpo), "sku", "nombre", "precio_venta", "unidad_medida")


def test_cuerpo_vacio_reporta_todos_los_obligatorios(cliente):
    verificar_422(
        post(cliente, {}),
        "sku", "nombre", "marca", "id_categoria", "unidad_medida", "precio_venta", "stock_minimo")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"data": "sku=ZZTEST-1", "content_type": "application/x-www-form-urlencoded"},
        {"data": "{no es json", "content_type": "application/json"},
        {"data": '["ZZTEST-1"]', "content_type": "application/json"},
        {},
    ],
)
def test_cuerpo_que_no_es_objeto_json_da_400(cliente, kwargs):
    respuesta = cliente.post("/productos", headers=CABECERAS, **kwargs)
    verificar_error(respuesta, 400, "PETICION_INVALIDA")


def test_sin_token_da_401(cliente, categoria):
    respuesta = cliente.post("/productos", json=cuerpo_valido(categoria))
    verificar_error(respuesta, 401, "NO_AUTENTICADO")
    assert filas_con_sku("ZZTEST-001") == []


def test_estado_y_campos_desconocidos_se_ignoran(cliente, categoria):
    cuerpo = cuerpo_valido(
        categoria, estado="INACTIVO", id_producto=999, creado_en="2000-01-01", extra=[1])
    respuesta = post(cliente, cuerpo)
    assert respuesta.status_code == 201
    producto = respuesta.get_json()
    assert producto["estado"] == "ACTIVO"
    assert producto["id_producto"] != 999
    assert set(producto) == CAMPOS
