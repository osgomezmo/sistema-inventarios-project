"""Pruebas de GET /bodegas y GET /bodegas/{id} contra el MySQL de desarrollo.

Los endpoints confirman sus propias transacciones, así que los datos de prueba
quedan guardados: todas las bodegas llevan el prefijo de código PREFIJO y un
fixture las borra al terminar (solo esas filas). Si MySQL no está disponible,
las pruebas se saltan.
"""

import pytest

from app import create_app
from app.config import cargar_configuracion
from app.db import abrir_conexion, transaccion
from app.errors import ApiError

PREFIJO = "ZZT-"
TOKEN = "token-de-prueba"
CABECERAS = {"Authorization": f"Bearer {TOKEN}"}
CAMPOS = {"id_bodega", "codigo", "nombre", "direccion", "estado"}
CONFIG = cargar_configuracion()


def patron_like(prefijo):
    # En LIKE, "_" y "%" son comodines: se escapan para filtrar solo el prefijo exacto.
    return prefijo.replace("\\", "\\\\").replace("_", "\\_").replace("%", "\\%") + "%"


def borrar_datos_de_prueba():
    with transaccion(CONFIG) as cur:
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


def crear_bodega(codigo, nombre, estado="ACTIVO", direccion="Calle 1 # 2-3"):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO bodegas (codigo, nombre, direccion, estado) VALUES (%s, %s, %s, %s)",
            (PREFIJO + codigo, nombre, direccion, estado),
        )
        return cur.lastrowid


@pytest.fixture
def bodegas():
    """Cuatro bodegas; dos comparten nombre para probar el desempate por id."""
    return {
        "b": crear_bodega("B", "ZZT Bodega B"),
        "a": crear_bodega("A", "ZZT Bodega A", direccion="Carrera 7 # 8-9"),
        "c1": crear_bodega("C1", "ZZT Bodega C", estado="INACTIVO"),
        "c2": crear_bodega("C2", "ZZT Bodega C"),
    }


def get(cliente, ruta, **params):
    return cliente.get(ruta, headers=CABECERAS, query_string=params)


def todas_las_paginas(cliente, per_page, **params):
    """Recorre el listado completo; devuelve las filas y los meta de cada página."""
    filas, metas, page = [], [], 1
    while True:
        cuerpo = get(cliente, "/bodegas", page=page, per_page=per_page, **params).get_json()
        filas.extend(cuerpo["data"])
        metas.append(cuerpo["meta"])
        if page * per_page >= cuerpo["meta"]["total"]:
            return filas, metas
        page += 1


def propias(filas):
    return [f["id_bodega"] for f in filas if f["codigo"].startswith(PREFIJO)]


def verificar_error(respuesta, status, codigo):
    assert respuesta.status_code == status
    error = respuesta.get_json()["error"]
    assert set(error) == {"codigo", "mensaje", "detalles"}
    assert error["codigo"] == codigo
    return error


# --- Listado ----------------------------------------------------------------


def test_listado_con_campos_exactos(cliente, bodegas):
    respuesta = get(cliente, "/bodegas", per_page=100)
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert set(cuerpo) == {"data", "meta"}
    assert set(cuerpo["meta"]) == {"page", "per_page", "total"}
    assert cuerpo["meta"]["page"] == 1 and cuerpo["meta"]["per_page"] == 100
    assert cuerpo["meta"]["total"] >= 4
    for fila in cuerpo["data"]:
        assert set(fila) == CAMPOS

    filas, _ = todas_las_paginas(cliente, 100)
    a = next(f for f in filas if f["id_bodega"] == bodegas["a"])
    assert a == {
        "id_bodega": bodegas["a"],
        "codigo": "ZZT-A",
        "nombre": "ZZT Bodega A",
        "direccion": "Carrera 7 # 8-9",
        "estado": "ACTIVO",
    }


def test_por_defecto_20_por_pagina(cliente, bodegas):
    assert get(cliente, "/bodegas").get_json()["meta"]["per_page"] == 20


def test_orden_por_nombre_y_luego_id(cliente, bodegas):
    filas, _ = todas_las_paginas(cliente, 100)
    assert propias(filas) == [bodegas["a"], bodegas["b"], bodegas["c1"], bodegas["c2"]]


def test_sin_estado_incluye_activas_e_inactivas(cliente, bodegas):
    filas, _ = todas_las_paginas(cliente, 100)
    estados = {f["id_bodega"]: f["estado"] for f in filas}
    assert estados[bodegas["c1"]] == "INACTIVO"
    assert estados[bodegas["c2"]] == "ACTIVO"


def test_filtro_estado(cliente, bodegas):
    activas, _ = todas_las_paginas(cliente, 100, estado="ACTIVO")
    inactivas, _ = todas_las_paginas(cliente, 100, estado="INACTIVO")
    assert propias(activas) == [bodegas["a"], bodegas["b"], bodegas["c2"]]
    assert propias(inactivas) == [bodegas["c1"]]
    assert all(f["estado"] == "ACTIVO" for f in activas)
    assert all(f["estado"] == "INACTIVO" for f in inactivas)


@pytest.mark.parametrize(
    "params, campo",
    [
        ({"estado": "BORRADA"}, "estado"),
        ({"estado": "activo"}, "estado"),
        ({"per_page": 101}, "per_page"),
        ({"per_page": 0}, "per_page"),
        ({"page": 0}, "page"),
        ({"page": "uno"}, "page"),
    ],
)
def test_filtros_invalidos_dan_422(cliente, params, campo):
    error = verificar_error(get(cliente, "/bodegas", **params), 422, "VALIDACION")
    assert list(error["detalles"]) == [campo]
    assert isinstance(error["detalles"][campo], list)


def test_varios_errores_se_reportan_juntos(cliente):
    error = verificar_error(
        get(cliente, "/bodegas", estado="x", per_page=101, page=0), 422, "VALIDACION")
    assert set(error["detalles"]) == {"estado", "per_page", "page"}


def test_paginacion_coherente(cliente, bodegas):
    paginadas, metas = todas_las_paginas(cliente, 2)
    completas, _ = todas_las_paginas(cliente, 100)
    ids = [f["id_bodega"] for f in paginadas]

    assert len(ids) == len(set(ids))  # ninguna fila se repite
    assert ids == [f["id_bodega"] for f in completas]  # mismo orden que sin paginar
    assert len(ids) == metas[0]["total"]  # la suma coincide con el total
    assert all(m["per_page"] == 2 for m in metas)
    assert [m["page"] for m in metas] == list(range(1, len(metas) + 1))


def test_pagina_mas_alla_del_final_da_lista_vacia(cliente, bodegas):
    total = get(cliente, "/bodegas").get_json()["meta"]["total"]
    cuerpo = get(cliente, "/bodegas", page=total + 1, per_page=1).get_json()
    assert cuerpo["data"] == []
    assert cuerpo["meta"] == {"page": total + 1, "per_page": 1, "total": total}


def test_texto_con_tildes_enie_y_comilla(cliente):
    nombre = "ZZT O'Brien ñandú"
    direccion = "Vía a Funza, km 2 'bodega 3'"
    id_bodega = crear_bodega("OBRIEN", nombre, direccion=direccion)
    cuerpo = get(cliente, f"/bodegas/{id_bodega}").get_json()
    assert (cuerpo["nombre"], cuerpo["direccion"]) == (nombre, direccion)
    assert nombre in get(cliente, "/bodegas", per_page=100).get_data(as_text=True)


# --- Consulta por id ----------------------------------------------------------


def test_obtener_por_id(cliente, bodegas):
    respuesta = get(cliente, f"/bodegas/{bodegas['c1']}")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "id_bodega": bodegas["c1"],
        "codigo": "ZZT-C1",
        "nombre": "ZZT Bodega C",
        "direccion": "Calle 1 # 2-3",
        "estado": "INACTIVO",
    }


def test_obtener_inexistente_da_404(cliente):
    error = verificar_error(get(cliente, "/bodegas/999999999"), 404, "NO_EXISTE")
    assert error["mensaje"] == "La bodega no existe."


@pytest.mark.parametrize("ruta", ["/bodegas/abc", "/bodegas/-1", "/bodegas/1.5"])
def test_id_no_entero_da_404(cliente, ruta):
    verificar_error(get(cliente, ruta), 404, "NO_EXISTE")


@pytest.mark.parametrize("ruta", ["/bodegas", "/bodegas/1"])
def test_sin_token_da_401(cliente, ruta):
    verificar_error(cliente.get(ruta), 401, "NO_AUTENTICADO")
