"""Pruebas de GET /stock y GET /stock/{sku} contra el MySQL de desarrollo.

Las bodegas de prueba llevan el prefijo de código PREFIJO y los saldos el
prefijo de SKU PREFIJO_SKU. Se insertan con SQL directo y un fixture borra al
terminar solo esas filas: primero saldos y luego bodegas. Si MySQL no está
disponible, las pruebas se saltan.
"""

import json
from decimal import Decimal

import pytest

from app import create_app
from app.config import cargar_configuracion
from app.db import abrir_conexion, transaccion
from app.errors import ApiError

PREFIJO = "ZZT-"
PREFIJO_SKU = "ZZTEST-"
TOKEN = "token-de-prueba"
CABECERAS = {"Authorization": f"Bearer {TOKEN}"}
CAMPOS = {"sku", "id_bodega", "cantidad", "costo_promedio", "valor", "stock_minimo", "bajo_minimo"}
CAMPOS_POR_BODEGA = {"id_bodega", "cantidad", "costo_promedio", "valor"}
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
def cliente():
    return create_app({"TESTING": True, "SERVICE_TOKEN": TOKEN}).test_client()


def crear_bodega(codigo, estado="ACTIVO"):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO bodegas (codigo, nombre, direccion, estado) VALUES (%s, %s, %s, %s)",
            (PREFIJO + codigo, f"Bodega {codigo}", "Calle 1", estado),
        )
        return cur.lastrowid


def crear_saldo(sku, id_bodega, cantidad, costo, minimo="0"):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO saldos (sku, id_bodega, cantidad, costo_promedio, stock_minimo)"
            " VALUES (%s, %s, %s, %s, %s)",
            (PREFIJO_SKU + sku, id_bodega, Decimal(cantidad), Decimal(costo), Decimal(minimo)),
        )


@pytest.fixture
def datos():
    """Tres bodegas (una inactiva) y saldos de dos SKU.

    A1: B1 2.500 x 3150.0000 (mín. 5, bajo), B2 3.000 x 0.3333 (mín. 3, igual: bajo),
        B3 inactiva 10.000 x 100.0000 (mín. 2, no bajo).
    B2: B1 0.000 x 50.0000 (mín. 0, igual: bajo).
    """
    b1, b2, b3 = crear_bodega("B1"), crear_bodega("B2"), crear_bodega("B3", "INACTIVO")
    crear_saldo("A1", b2, "3.000", "0.3333", "3")
    crear_saldo("A1", b1, "2.500", "3150.0000", "5")
    crear_saldo("A1", b3, "10.000", "100.0000", "2")
    crear_saldo("B2", b1, "0.000", "50.0000", "0")
    return {"b1": b1, "b2": b2, "b3": b3}


def get(cliente, ruta, **params):
    return cliente.get(ruta, headers=CABECERAS, query_string=params)


def listar(cliente, **params):
    respuesta = get(cliente, "/stock", **params)
    assert respuesta.status_code == 200, respuesta.get_json()
    return respuesta.get_json()


def todas_las_paginas(cliente, per_page, **params):
    filas, metas, page = [], [], 1
    while True:
        cuerpo = listar(cliente, page=page, per_page=per_page, **params)
        filas.extend(cuerpo["data"])
        metas.append(cuerpo["meta"])
        if page * per_page >= cuerpo["meta"]["total"]:
            return filas, metas
        page += 1


def propias(filas):
    return [(f["sku"], f["id_bodega"]) for f in filas if f["sku"].startswith(PREFIJO_SKU)]


def verificar_error(respuesta, status, codigo):
    assert respuesta.status_code == status, respuesta.get_json()
    error = respuesta.get_json()["error"]
    assert set(error) == {"codigo", "mensaje", "detalles"}
    assert error["codigo"] == codigo
    return error


# --- Listado ----------------------------------------------------------------


def test_listado_de_un_sku_con_campos_exactos(cliente, datos):
    respuesta = get(cliente, "/stock", sku="ZZTEST-A1")
    cuerpo = json.loads(respuesta.get_data(as_text=True))
    assert set(cuerpo) == {"data", "meta"}
    assert cuerpo["meta"] == {"page": 1, "per_page": 20, "total": 3}
    for fila in cuerpo["data"]:
        assert set(fila) == CAMPOS
        for campo in ("cantidad", "costo_promedio", "valor", "stock_minimo"):
            assert isinstance(fila[campo], (int, float)) and not isinstance(fila[campo], bool)
        assert isinstance(fila["bajo_minimo"], bool)


def test_valor_y_bajo_minimo(cliente, datos):
    filas = {f["id_bodega"]: f for f in listar(cliente, sku="ZZTEST-A1")["data"]}
    b1, b2, b3 = filas[datos["b1"]], filas[datos["b2"]], filas[datos["b3"]]

    assert (b1["cantidad"], b1["costo_promedio"], b1["valor"]) == (2.5, 3150.0, 7875.0)
    assert (b2["cantidad"], b2["costo_promedio"], b2["valor"]) == (3.0, 0.3333, 1.0)
    assert b3["valor"] == 1000.0
    assert b1["bajo_minimo"] is True   # 2.5 < 5
    assert b2["bajo_minimo"] is True   # 3 = 3
    assert b3["bajo_minimo"] is False  # 10 > 2
    assert b1["stock_minimo"] == 5


def test_orden_por_sku_y_bodega(cliente, datos):
    filas, _ = todas_las_paginas(cliente, 100)
    assert propias(filas) == [
        ("ZZTEST-A1", datos["b1"]), ("ZZTEST-A1", datos["b2"]), ("ZZTEST-A1", datos["b3"]),
        ("ZZTEST-B2", datos["b1"]),
    ]


def test_bodega_inactiva_y_saldo_en_cero_aparecen(cliente, datos):
    filas, _ = todas_las_paginas(cliente, 100)
    assert ("ZZTEST-A1", datos["b3"]) in propias(filas)
    cero = next(f for f in filas if f["sku"] == "ZZTEST-B2")
    assert cero["cantidad"] == 0 and cero["valor"] == 0


@pytest.mark.parametrize("sku", ["ZZTEST-A1", "zztest-a1", "  ZZTEST-A1  "])
def test_filtro_sku_exacto(cliente, datos, sku):
    cuerpo = listar(cliente, sku=sku)
    assert {f["sku"] for f in cuerpo["data"]} == {"ZZTEST-A1"}
    assert cuerpo["meta"]["total"] == 3


def test_filtro_sku_no_es_parcial(cliente, datos):
    assert listar(cliente, sku="ZZTEST-A")["meta"]["total"] == 0


@pytest.mark.parametrize("sku", ["", "   "])
def test_filtro_sku_vacio_se_ignora(cliente, datos, sku):
    assert listar(cliente, sku=sku, per_page=100)["meta"]["total"] >= 4


def test_filtro_id_bodega(cliente, datos):
    filas, _ = todas_las_paginas(cliente, 100, id_bodega=datos["b1"])
    assert propias(filas) == [("ZZTEST-A1", datos["b1"]), ("ZZTEST-B2", datos["b1"])]
    assert all(f["id_bodega"] == datos["b1"] for f in filas)


def test_id_bodega_inexistente_da_lista_vacia(cliente, datos):
    assert listar(cliente, id_bodega=999_999_999) == {
        "data": [], "meta": {"page": 1, "per_page": 20, "total": 0}}


@pytest.mark.parametrize("valor", ["true", "TRUE", " True "])
def test_filtro_bajo_minimo_true(cliente, datos, valor):
    filas, _ = todas_las_paginas(cliente, 100, bajo_minimo=valor)
    assert propias(filas) == [
        ("ZZTEST-A1", datos["b1"]), ("ZZTEST-A1", datos["b2"]), ("ZZTEST-B2", datos["b1"])]
    assert all(f["bajo_minimo"] for f in filas)


def test_filtro_bajo_minimo_false(cliente, datos):
    filas, _ = todas_las_paginas(cliente, 100, bajo_minimo="false")
    assert propias(filas) == [("ZZTEST-A1", datos["b3"])]
    assert not any(f["bajo_minimo"] for f in filas)


def test_filtros_combinados(cliente, datos):
    cuerpo = listar(cliente, sku="zztest-a1", id_bodega=datos["b1"], bajo_minimo="true")
    assert propias(cuerpo["data"]) == [("ZZTEST-A1", datos["b1"])]
    assert listar(cliente, sku="ZZTEST-A1", id_bodega=datos["b3"], bajo_minimo="true")["data"] == []


@pytest.mark.parametrize(
    "params, campo",
    [
        ({"bajo_minimo": "maybe"}, "bajo_minimo"),
        ({"bajo_minimo": "1"}, "bajo_minimo"),
        ({"id_bodega": "abc"}, "id_bodega"),
        ({"id_bodega": "1.5"}, "id_bodega"),
        ({"per_page": 101}, "per_page"),
        ({"page": 0}, "page"),
        ({"sku": "X" * 51}, "sku"),
    ],
)
def test_filtros_invalidos_dan_422(cliente, params, campo):
    error = verificar_error(get(cliente, "/stock", **params), 422, "VALIDACION")
    assert list(error["detalles"]) == [campo]


def test_varios_errores_juntos(cliente):
    error = verificar_error(
        get(cliente, "/stock", bajo_minimo="maybe", id_bodega="abc", per_page=101),
        422, "VALIDACION")
    assert set(error["detalles"]) == {"bajo_minimo", "id_bodega", "per_page"}


def test_paginacion_coherente(cliente, datos):
    paginadas, metas = todas_las_paginas(cliente, 2)
    completas, _ = todas_las_paginas(cliente, 100)
    claves = [(f["sku"], f["id_bodega"]) for f in paginadas]

    assert len(claves) == len(set(claves))
    assert claves == [(f["sku"], f["id_bodega"]) for f in completas]
    assert len(claves) == metas[0]["total"]
    assert [m["page"] for m in metas] == list(range(1, len(metas) + 1))


def test_pagina_mas_alla_del_final(cliente, datos):
    cuerpo = listar(cliente, sku="ZZTEST-A1", per_page=2, page=3)
    assert cuerpo["data"] == [] and cuerpo["meta"]["total"] == 3


# --- Por SKU ------------------------------------------------------------------


def test_stock_de_sku(cliente, datos):
    respuesta = get(cliente, "/stock/ZZTEST-A1")
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert set(cuerpo) == {"sku", "por_bodega", "total"}
    assert set(cuerpo["total"]) == {"cantidad", "valor"}
    assert cuerpo["sku"] == "ZZTEST-A1"
    assert all(set(b) == CAMPOS_POR_BODEGA for b in cuerpo["por_bodega"])
    assert [b["id_bodega"] for b in cuerpo["por_bodega"]] == [datos["b1"], datos["b2"], datos["b3"]]
    assert [b["valor"] for b in cuerpo["por_bodega"]] == [7875.0, 1.0, 1000.0]
    # Suma de cantidades y suma de los valores ya redondeados.
    assert cuerpo["total"] == {"cantidad": 15.5, "valor": 8876.0}


def test_stock_de_sku_solo_trae_ese_sku(cliente, datos):
    cuerpo = get(cliente, "/stock/ZZTEST-B2").get_json()
    assert cuerpo["sku"] == "ZZTEST-B2"
    assert [b["id_bodega"] for b in cuerpo["por_bodega"]] == [datos["b1"]]


def test_stock_de_sku_en_minusculas_devuelve_el_guardado(cliente, datos):
    respuesta = get(cliente, "/stock/zztest-a1")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["sku"] == "ZZTEST-A1"


def test_saldo_en_cero_cuenta(cliente, datos):
    respuesta = get(cliente, "/stock/ZZTEST-B2")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["total"] == {"cantidad": 0, "valor": 0}


@pytest.mark.parametrize("sku", ["ZZTEST-NOEXISTE", "ZZTEST-" + "X" * 44])
def test_sku_sin_saldos_da_404(cliente, sku):
    error = verificar_error(get(cliente, f"/stock/{sku}"), 404, "NO_EXISTE")
    assert error["mensaje"] == "No hay saldos para ese SKU."


def test_sku_demasiado_largo_da_404(cliente):
    error = verificar_error(get(cliente, "/stock/" + "X" * 51), 404, "NO_EXISTE")
    assert error["mensaje"] == "No hay saldos para ese SKU."


# --- Autenticación y métodos --------------------------------------------------


@pytest.mark.parametrize("ruta", ["/stock", "/stock/ZZTEST-A1"])
def test_sin_token_da_401(cliente, ruta):
    verificar_error(cliente.get(ruta), 401, "NO_AUTENTICADO")


@pytest.mark.parametrize("ruta", ["/stock", "/stock/ZZTEST-A1"])
def test_post_no_permitido_da_405(cliente, ruta):
    verificar_error(cliente.post(ruta, headers=CABECERAS), 405, "METODO_NO_PERMITIDO")
