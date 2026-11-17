"""Pruebas de GET /categorias y GET /categorias/{id} contra el MySQL de desarrollo.

Los endpoints abren su propia conexión, así que los datos de prueba se crean y
confirman de verdad. Todos llevan el prefijo PREFIJO en el nombre y un fixture
los borra al terminar (solo esas filas). Si MySQL no está disponible, las
pruebas se saltan.
"""

import pytest

from app import create_app
from app.config import cargar_configuracion
from app.db import abrir_conexion, transaccion
from app.errors import ApiError

PREFIJO = "zz_test_"
TOKEN = "token-de-prueba"
CABECERAS = {"Authorization": f"Bearer {TOKEN}"}
CAMPOS = {"id_categoria", "nombre", "descripcion", "id_categoria_padre", "estado"}
CAMPOS_RAIZ = CAMPOS | {"subcategorias"}
CONFIG = cargar_configuracion()


def borrar_datos_de_prueba():
    # En LIKE, "_" es comodín: se escapa para borrar solo el prefijo exacto.
    patron = PREFIJO.replace("_", "\\_") + "%"
    with transaccion(CONFIG) as cur:
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


@pytest.fixture
def cliente():
    app = create_app({"TESTING": True, "SERVICE_TOKEN": TOKEN})
    return app.test_client()


@pytest.fixture
def crear():
    """Crea categorías con el prefijo de prueba y las borra al terminar."""
    borrar_datos_de_prueba()

    def _crear(nombre, id_padre=None, estado="ACTIVO", descripcion=None):
        with transaccion(CONFIG) as cur:
            cur.execute(
                "INSERT INTO categorias (nombre, descripcion, id_categoria_padre, estado)"
                " VALUES (%s, %s, %s, %s)",
                (PREFIJO + nombre, descripcion, id_padre, estado),
            )
            return cur.lastrowid

    yield _crear
    borrar_datos_de_prueba()


def get(cliente, ruta, **params):
    return cliente.get(ruta, headers=CABECERAS, query_string=params)


def todas_las_raices(cliente, **params):
    """Recorre todas las páginas del listado para no depender de otros datos."""
    filas, page = [], 1
    while True:
        cuerpo = get(cliente, "/categorias", page=page, per_page=100, **params).get_json()
        filas.extend(cuerpo["data"])
        if page * 100 >= cuerpo["meta"]["total"]:
            return filas, cuerpo["meta"]["total"]
        page += 1


def propias(filas):
    return [f for f in filas if f["nombre"].startswith(PREFIJO)]


def verificar_error(respuesta, status, codigo):
    assert respuesta.status_code == status
    error = respuesta.get_json()["error"]
    assert set(error) == {"codigo", "mensaje", "detalles"}
    assert error["codigo"] == codigo
    return error


# --- Listado ----------------------------------------------------------------


def test_listado_con_subcategorias_anidadas_y_ordenadas(cliente, crear):
    id_b = crear("b_bebidas", descripcion="Bebidas")
    id_a = crear("a_lacteos")
    crear("a_lacteos_yogures", id_a)
    crear("a_lacteos_leches", id_a)

    respuesta = get(cliente, "/categorias", per_page=100)
    assert respuesta.status_code == 200
    assert set(respuesta.get_json()) == {"data", "meta"}
    assert set(respuesta.get_json()["meta"]) == {"page", "per_page", "total"}

    filas, total = todas_las_raices(cliente)
    mias = propias(filas)
    assert total >= 2
    assert [f["id_categoria"] for f in mias] == [id_a, id_b]
    for fila in filas:
        assert set(fila) == CAMPOS_RAIZ
        assert fila["id_categoria_padre"] is None
        for sub in fila["subcategorias"]:
            assert set(sub) == CAMPOS

    lacteos, bebidas = mias
    assert [s["nombre"] for s in lacteos["subcategorias"]] == [
        PREFIJO + "a_lacteos_leches", PREFIJO + "a_lacteos_yogures"]
    assert all(s["id_categoria_padre"] == id_a for s in lacteos["subcategorias"])
    assert bebidas["subcategorias"] == []
    assert bebidas["descripcion"] == "Bebidas"
    assert lacteos["descripcion"] is None


def test_filtro_estado_aplica_a_raices_y_subcategorias(cliente, crear):
    id_activa = crear("activa")
    crear("activa_sub_activa", id_activa)
    crear("activa_sub_inactiva", id_activa, estado="INACTIVO")
    id_inactiva = crear("inactiva", estado="INACTIVO")
    crear("inactiva_sub", id_inactiva)

    activas = propias(todas_las_raices(cliente, estado="ACTIVO")[0])
    assert [f["id_categoria"] for f in activas] == [id_activa]
    assert [s["nombre"] for s in activas[0]["subcategorias"]] == [
        PREFIJO + "activa_sub_activa"]

    inactivas = propias(todas_las_raices(cliente, estado="INACTIVO")[0])
    assert [f["id_categoria"] for f in inactivas] == [id_inactiva]
    assert inactivas[0]["subcategorias"] == []

    todas = propias(todas_las_raices(cliente)[0])
    assert {f["id_categoria"] for f in todas} == {id_activa, id_inactiva}
    assert len(todas[0]["subcategorias"]) == 2


def test_filtro_id_padre_devuelve_lista_plana(cliente, crear):
    id_padre = crear("padre")
    id_y = crear("padre_y", id_padre)
    id_x = crear("padre_x", id_padre, estado="INACTIVO")
    crear("otra_raiz")

    cuerpo = get(cliente, "/categorias", id_padre=id_padre).get_json()
    assert cuerpo["meta"] == {"page": 1, "per_page": 20, "total": 2}
    assert [f["id_categoria"] for f in cuerpo["data"]] == [id_x, id_y]
    for fila in cuerpo["data"]:
        assert set(fila) == CAMPOS
        assert fila["id_categoria_padre"] == id_padre

    solo_activas = get(cliente, "/categorias", id_padre=id_padre, estado="ACTIVO").get_json()
    assert [f["id_categoria"] for f in solo_activas["data"]] == [id_y]
    assert solo_activas["meta"]["total"] == 1


def test_id_padre_inexistente_da_lista_vacia(cliente):
    respuesta = get(cliente, "/categorias", id_padre=999_999_999)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "data": [], "meta": {"page": 1, "per_page": 20, "total": 0}}


def test_paginacion(cliente, crear):
    id_padre = crear("pag")
    ids = [crear(f"pag_{letra}", id_padre) for letra in "abc"]

    primera = get(cliente, "/categorias", id_padre=id_padre, per_page=2).get_json()
    assert primera["meta"] == {"page": 1, "per_page": 2, "total": 3}
    assert [f["id_categoria"] for f in primera["data"]] == ids[:2]

    segunda = get(cliente, "/categorias", id_padre=id_padre, per_page=2, page=2).get_json()
    assert segunda["meta"] == {"page": 2, "per_page": 2, "total": 3}
    assert [f["id_categoria"] for f in segunda["data"]] == ids[2:]

    tercera = get(cliente, "/categorias", id_padre=id_padre, per_page=2, page=3).get_json()
    assert tercera["data"] == [] and tercera["meta"]["total"] == 3


def test_paginacion_de_raices(cliente, crear):
    for letra in "abc":
        crear(f"raiz_{letra}")

    cuerpo = get(cliente, "/categorias", per_page=2, page=2).get_json()
    assert cuerpo["meta"]["page"] == 2 and cuerpo["meta"]["per_page"] == 2
    assert cuerpo["meta"]["total"] >= 3
    assert len(cuerpo["data"]) <= 2


@pytest.mark.parametrize(
    "params, campo",
    [
        ({"page": 0}, "page"),
        ({"per_page": 101}, "per_page"),
        ({"per_page": "muchos"}, "per_page"),
        ({"estado": "BORRADO"}, "estado"),
        ({"id_padre": "abc"}, "id_padre"),
        ({"id_padre": "1.5"}, "id_padre"),
    ],
)
def test_filtros_invalidos_responden_422(cliente, params, campo):
    error = verificar_error(get(cliente, "/categorias", **params), 422, "VALIDACION")
    assert list(error["detalles"]) == [campo]
    assert isinstance(error["detalles"][campo], list)


def test_varios_filtros_invalidos_se_reportan_juntos(cliente):
    error = verificar_error(
        get(cliente, "/categorias", page=0, estado="x", id_padre="y"), 422, "VALIDACION")
    assert set(error["detalles"]) == {"page", "estado", "id_padre"}


# --- Consulta por id ----------------------------------------------------------


def test_obtener_raiz_incluye_todas_sus_subcategorias(cliente, crear):
    id_raiz = crear("raiz", descripcion="Raíz de prueba")
    id_b = crear("raiz_b", id_raiz, estado="INACTIVO")
    id_a = crear("raiz_a", id_raiz)

    respuesta = get(cliente, f"/categorias/{id_raiz}")
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert set(cuerpo) == CAMPOS_RAIZ
    assert cuerpo["id_categoria"] == id_raiz
    assert cuerpo["nombre"] == PREFIJO + "raiz"
    assert cuerpo["descripcion"] == "Raíz de prueba"
    assert cuerpo["id_categoria_padre"] is None
    assert cuerpo["estado"] == "ACTIVO"
    assert [s["id_categoria"] for s in cuerpo["subcategorias"]] == [id_a, id_b]
    assert all(set(s) == CAMPOS for s in cuerpo["subcategorias"])


def test_obtener_subcategoria_no_lleva_subcategorias(cliente, crear):
    id_raiz = crear("raiz")
    id_sub = crear("raiz_sub", id_raiz)

    cuerpo = get(cliente, f"/categorias/{id_sub}").get_json()
    assert set(cuerpo) == CAMPOS
    assert cuerpo["id_categoria_padre"] == id_raiz


def test_obtener_inexistente_responde_404(cliente):
    error = verificar_error(get(cliente, "/categorias/999999999"), 404, "NO_EXISTE")
    assert error["mensaje"] == "La categoría no existe."


@pytest.mark.parametrize("ruta", ["/categorias/abc", "/categorias/-1", "/categorias/1.5"])
def test_id_no_entero_responde_404(cliente, ruta):
    verificar_error(get(cliente, ruta), 404, "NO_EXISTE")


@pytest.mark.parametrize("ruta", ["/categorias", "/categorias/1"])
def test_sin_token_responde_401(cliente, ruta):
    verificar_error(cliente.get(ruta), 401, "NO_AUTENTICADO")
