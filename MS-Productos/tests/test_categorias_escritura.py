"""Pruebas de POST /categorias y PUT /categorias/{id} contra el MySQL de desarrollo.

Los endpoints confirman sus propias transacciones, así que los datos de prueba
quedan guardados: todos llevan el prefijo PREFIJO en el nombre y un fixture los
borra al terminar (solo esas filas). Si MySQL no está disponible, las pruebas
se saltan.
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


@pytest.fixture(autouse=True)
def limpiar():
    borrar_datos_de_prueba()
    yield
    borrar_datos_de_prueba()


@pytest.fixture
def cliente():
    return create_app({"TESTING": True, "SERVICE_TOKEN": TOKEN}).test_client()


def crear_sql(nombre, id_padre=None, estado="ACTIVO"):
    """Crea una categoría directo en la base, para preparar escenarios."""
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO categorias (nombre, id_categoria_padre, estado) VALUES (%s, %s, %s)",
            (PREFIJO + nombre, id_padre, estado),
        )
        return cur.lastrowid


def leer_sql(id_categoria):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "SELECT nombre, descripcion, id_categoria_padre, estado FROM categorias"
            " WHERE id_categoria = %s",
            (id_categoria,),
        )
        return cur.fetchone()


def post(cliente, cuerpo, **kwargs):
    return cliente.post("/categorias", headers=CABECERAS, json=cuerpo, **kwargs)


def put(cliente, id_categoria, cuerpo):
    return cliente.put(f"/categorias/{id_categoria}", headers=CABECERAS, json=cuerpo)


def verificar_error(respuesta, status, codigo):
    assert respuesta.status_code == status
    error = respuesta.get_json()["error"]
    assert set(error) == {"codigo", "mensaje", "detalles"}
    assert error["codigo"] == codigo
    return error


# --- POST ---------------------------------------------------------------------


def test_crea_raiz(cliente):
    respuesta = post(cliente, {"nombre": PREFIJO + "lacteos", "descripcion": "Leche y derivados"})
    assert respuesta.status_code == 201
    cuerpo = respuesta.get_json()
    assert set(cuerpo) == CAMPOS_RAIZ
    assert cuerpo["nombre"] == PREFIJO + "lacteos"
    assert cuerpo["descripcion"] == "Leche y derivados"
    assert cuerpo["id_categoria_padre"] is None
    assert cuerpo["estado"] == "ACTIVO"
    assert cuerpo["subcategorias"] == []
    assert leer_sql(cuerpo["id_categoria"])["nombre"] == PREFIJO + "lacteos"


def test_crea_subcategoria(cliente):
    id_raiz = crear_sql("raiz")
    respuesta = post(cliente, {"nombre": PREFIJO + "sub", "id_categoria_padre": id_raiz})
    assert respuesta.status_code == 201
    cuerpo = respuesta.get_json()
    assert set(cuerpo) == CAMPOS
    assert cuerpo["id_categoria_padre"] == id_raiz
    assert cuerpo["descripcion"] is None


def test_nombre_se_recorta(cliente):
    cuerpo = post(cliente, {"nombre": f"   {PREFIJO}espacios  "}).get_json()
    assert cuerpo["nombre"] == PREFIJO + "espacios"


def test_nombre_con_tildes_enie_y_comilla(cliente):
    nombre = PREFIJO + "O'Brien ñandú"
    cuerpo = post(cliente, {"nombre": nombre}).get_json()
    assert cuerpo["nombre"] == nombre
    assert leer_sql(cuerpo["id_categoria"])["nombre"] == nombre


@pytest.mark.parametrize(
    "repetido",
    [PREFIJO + "Lácteos", PREFIJO + "lácteos", PREFIJO + "LACTEOS", PREFIJO + "lacteos"],
)
def test_nombre_repetido_en_la_raiz_da_409(cliente, repetido):
    crear_sql("Lácteos")
    error = verificar_error(post(cliente, {"nombre": repetido}), 409, "NOMBRE_REPETIDO")
    assert list(error["detalles"]) == ["nombre"]


def test_nombre_repetido_bajo_el_mismo_padre_da_409(cliente):
    id_raiz = crear_sql("raiz")
    crear_sql("leches", id_raiz)
    respuesta = post(cliente, {"nombre": PREFIJO + "Leches", "id_categoria_padre": id_raiz})
    verificar_error(respuesta, 409, "NOMBRE_REPETIDO")


def test_mismo_nombre_bajo_otro_padre_se_permite(cliente):
    id_a = crear_sql("a")
    id_b = crear_sql("b")
    crear_sql("comun", id_a)
    respuesta = post(cliente, {"nombre": PREFIJO + "comun", "id_categoria_padre": id_b})
    assert respuesta.status_code == 201
    # Y una raíz con el mismo nombre que una subcategoría también.
    assert post(cliente, {"nombre": PREFIJO + "comun"}).status_code == 201


@pytest.mark.parametrize("caso", ["inexistente", "inactivo", "tercer_nivel"])
def test_padre_invalido_da_422(cliente, caso):
    if caso == "inexistente":
        id_padre = 999_999_999
    elif caso == "inactivo":
        id_padre = crear_sql("inactiva", estado="INACTIVO")
    else:
        id_padre = crear_sql("sub", crear_sql("raiz"))

    respuesta = post(cliente, {"nombre": PREFIJO + "hija", "id_categoria_padre": id_padre})
    error = verificar_error(respuesta, 422, "VALIDACION")
    assert list(error["detalles"]) == ["id_categoria_padre"]


@pytest.mark.parametrize(
    "cuerpo, campo",
    [
        ({}, "nombre"),
        ({"nombre": ""}, "nombre"),
        ({"nombre": "   "}, "nombre"),
        ({"nombre": "x" * 101}, "nombre"),
        ({"nombre": 15}, "nombre"),
        ({"nombre": PREFIJO + "ok", "descripcion": "x" * 256}, "descripcion"),
        ({"nombre": PREFIJO + "ok", "id_categoria_padre": "abc"}, "id_categoria_padre"),
        ({"nombre": PREFIJO + "ok", "id_categoria_padre": 1.5}, "id_categoria_padre"),
        ({"nombre": PREFIJO + "ok", "id_categoria_padre": True}, "id_categoria_padre"),
    ],
)
def test_campos_invalidos_dan_422(cliente, cuerpo, campo):
    error = verificar_error(post(cliente, cuerpo), 422, "VALIDACION")
    assert list(error["detalles"]) == [campo]


def test_limites_exactos_se_aceptan(cliente):
    nombre = PREFIJO + "x" * (100 - len(PREFIJO))
    respuesta = post(cliente, {"nombre": nombre, "descripcion": "d" * 255})
    assert respuesta.status_code == 201


def test_varios_errores_se_reportan_juntos(cliente):
    respuesta = post(
        cliente, {"nombre": "", "descripcion": "x" * 256, "id_categoria_padre": "abc"})
    error = verificar_error(respuesta, 422, "VALIDACION")
    assert set(error["detalles"]) == {"nombre", "descripcion", "id_categoria_padre"}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"data": "nombre=algo", "content_type": "application/x-www-form-urlencoded"},
        {"data": "{no es json", "content_type": "application/json"},
        {"data": '["zz_test_lista"]', "content_type": "application/json"},
        {},
    ],
)
def test_cuerpo_que_no_es_objeto_json_da_400(cliente, kwargs):
    respuesta = cliente.post("/categorias", headers=CABECERAS, **kwargs)
    verificar_error(respuesta, 400, "PETICION_INVALIDA")


def test_post_sin_token_da_401(cliente):
    respuesta = cliente.post("/categorias", json={"nombre": PREFIJO + "sin_token"})
    verificar_error(respuesta, 401, "NO_AUTENTICADO")


# --- PUT ----------------------------------------------------------------------


def test_put_cambia_nombre_y_descripcion(cliente):
    id_raiz = crear_sql("viejo")
    crear_sql("hija", id_raiz)
    respuesta = put(cliente, id_raiz, {"nombre": PREFIJO + "nuevo", "descripcion": "Otra"})
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert set(cuerpo) == CAMPOS_RAIZ
    assert (cuerpo["nombre"], cuerpo["descripcion"]) == (PREFIJO + "nuevo", "Otra")
    assert [s["nombre"] for s in cuerpo["subcategorias"]] == [PREFIJO + "hija"]


def test_put_reemplaza_todo_y_deja_null_lo_que_no_viene(cliente):
    id_raiz = crear_sql("raiz")
    respuesta = post(
        cliente,
        {"nombre": PREFIJO + "sub", "descripcion": "Antes", "id_categoria_padre": id_raiz},
    )
    id_sub = respuesta.get_json()["id_categoria"]

    cuerpo = put(cliente, id_sub, {"nombre": PREFIJO + "sub"}).get_json()
    assert cuerpo["descripcion"] is None
    assert cuerpo["id_categoria_padre"] is None
    assert set(cuerpo) == CAMPOS_RAIZ


def test_put_inexistente_da_404(cliente):
    error = verificar_error(
        put(cliente, 999_999_999, {"nombre": PREFIJO + "x"}), 404, "NO_EXISTE")
    assert error["mensaje"] == "La categoría no existe."


def test_put_nombre_repetido_da_409(cliente):
    crear_sql("ocupado")
    id_otra = crear_sql("otra")
    respuesta = put(cliente, id_otra, {"nombre": PREFIJO + "OCUPADO"})
    verificar_error(respuesta, 409, "NOMBRE_REPETIDO")
    assert leer_sql(id_otra)["nombre"] == PREFIJO + "otra"


def test_put_con_su_propio_nombre_es_valido(cliente):
    id_raiz = crear_sql("mismo")
    respuesta = put(cliente, id_raiz, {"nombre": PREFIJO + "Mismo", "descripcion": "Cambia"})
    assert respuesta.status_code == 200
    assert respuesta.get_json()["nombre"] == PREFIJO + "Mismo"


def test_put_su_propio_padre_da_422(cliente):
    id_raiz = crear_sql("raiz")
    respuesta = put(cliente, id_raiz, {"nombre": PREFIJO + "raiz", "id_categoria_padre": id_raiz})
    error = verificar_error(respuesta, 422, "VALIDACION")
    assert list(error["detalles"]) == ["id_categoria_padre"]


def test_put_raiz_con_subcategorias_no_pasa_a_subcategoria(cliente):
    id_a = crear_sql("a")
    crear_sql("a_hija", id_a)
    id_b = crear_sql("b")
    respuesta = put(cliente, id_a, {"nombre": PREFIJO + "a", "id_categoria_padre": id_b})
    error = verificar_error(respuesta, 422, "VALIDACION")
    assert list(error["detalles"]) == ["id_categoria_padre"]
    assert leer_sql(id_a)["id_categoria_padre"] is None


def test_put_raiz_sin_subcategorias_pasa_a_subcategoria(cliente):
    id_a = crear_sql("a")
    id_b = crear_sql("b")
    respuesta = put(cliente, id_a, {"nombre": PREFIJO + "a", "id_categoria_padre": id_b})
    assert respuesta.status_code == 200
    assert set(respuesta.get_json()) == CAMPOS


def test_put_mueve_subcategoria_a_otra_raiz(cliente):
    id_a = crear_sql("a")
    id_b = crear_sql("b")
    id_sub = crear_sql("sub", id_a)
    respuesta = put(cliente, id_sub, {"nombre": PREFIJO + "sub", "id_categoria_padre": id_b})
    assert respuesta.status_code == 200
    assert respuesta.get_json()["id_categoria_padre"] == id_b
    assert leer_sql(id_sub)["id_categoria_padre"] == id_b


def test_put_mover_a_raiz_inactiva_da_422(cliente):
    id_a = crear_sql("a")
    id_inactiva = crear_sql("inactiva", estado="INACTIVO")
    id_sub = crear_sql("sub", id_a)
    respuesta = put(
        cliente, id_sub, {"nombre": PREFIJO + "sub", "id_categoria_padre": id_inactiva})
    verificar_error(respuesta, 422, "VALIDACION")


def test_put_convierte_subcategoria_en_raiz(cliente):
    id_a = crear_sql("a")
    id_sub = crear_sql("sub", id_a)
    respuesta = put(cliente, id_sub, {"nombre": PREFIJO + "sub", "id_categoria_padre": None})
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["id_categoria_padre"] is None
    assert cuerpo["subcategorias"] == []


def test_put_mover_choca_con_nombre_del_nuevo_nivel(cliente):
    id_a = crear_sql("a")
    crear_sql("sub")  # raíz con el mismo nombre
    id_sub = crear_sql("sub", id_a)
    respuesta = put(cliente, id_sub, {"nombre": PREFIJO + "sub"})
    verificar_error(respuesta, 409, "NOMBRE_REPETIDO")


def test_put_ignora_estado_y_campos_desconocidos(cliente):
    id_raiz = crear_sql("raiz")
    respuesta = put(
        cliente, id_raiz,
        {"nombre": PREFIJO + "raiz", "estado": "INACTIVO", "otro": 1, "id_categoria": 5},
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["estado"] == "ACTIVO"
    assert cuerpo["id_categoria"] == id_raiz
    assert leer_sql(id_raiz)["estado"] == "ACTIVO"


def test_put_no_reactiva_una_categoria_inactiva(cliente):
    id_raiz = crear_sql("inactiva", estado="INACTIVO")
    cuerpo = put(cliente, id_raiz, {"nombre": PREFIJO + "inactiva", "estado": "ACTIVO"}).get_json()
    assert cuerpo["estado"] == "INACTIVO"


def test_put_valida_campos(cliente):
    id_raiz = crear_sql("raiz")
    error = verificar_error(put(cliente, id_raiz, {"descripcion": 5}), 422, "VALIDACION")
    assert set(error["detalles"]) == {"nombre", "descripcion"}


def test_put_cuerpo_no_json_da_400(cliente):
    id_raiz = crear_sql("raiz")
    respuesta = cliente.put(
        f"/categorias/{id_raiz}", headers=CABECERAS, data="texto", content_type="text/plain")
    verificar_error(respuesta, 400, "PETICION_INVALIDA")


def test_put_sin_token_da_401(cliente):
    verificar_error(
        cliente.put("/categorias/1", json={"nombre": PREFIJO + "x"}), 401, "NO_AUTENTICADO")
