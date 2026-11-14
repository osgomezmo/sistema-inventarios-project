"""Pruebas de POST /bodegas y PUT /bodegas/{id} contra el MySQL de desarrollo.

Los endpoints confirman sus propias transacciones: todas las bodegas de prueba
llevan el prefijo de código PREFIJO y un fixture las borra al terminar (solo
esas filas). Si MySQL no está disponible, las pruebas se saltan.
"""

import threading

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
QUITAR = object()


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
def app():
    return create_app({"TESTING": True, "SERVICE_TOKEN": TOKEN})


@pytest.fixture
def cliente(app):
    return app.test_client()


def crear_sql(codigo, estado="ACTIVO"):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO bodegas (codigo, nombre, direccion, estado) VALUES (%s, %s, %s, %s)",
            (PREFIJO + codigo, "Bodega original", "Dirección original", estado),
        )
        return cur.lastrowid


def leer_sql(id_bodega):
    with transaccion(CONFIG) as cur:
        cur.execute("SELECT * FROM bodegas WHERE id_bodega = %s", (id_bodega,))
        return cur.fetchone()


def filas_con_codigo(codigo):
    with transaccion(CONFIG) as cur:
        cur.execute("SELECT id_bodega FROM bodegas WHERE codigo = %s", (codigo,))
        return cur.fetchall()


def cuerpo(**cambios):
    datos = {"codigo": "ZZT-NORTE", "nombre": "Bodega Norte", "direccion": "Calle 80 # 10-20"}
    datos.update(cambios)
    return {k: v for k, v in datos.items() if v is not QUITAR}


def post(cliente, datos, **kwargs):
    return cliente.post("/bodegas", headers=CABECERAS, json=datos, **kwargs)


def put(cliente, id_bodega, datos):
    return cliente.put(f"/bodegas/{id_bodega}", headers=CABECERAS, json=datos)


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


# --- POST ---------------------------------------------------------------------


def test_crea_bodega(cliente):
    respuesta = post(cliente, cuerpo())
    assert respuesta.status_code == 201
    bodega = respuesta.get_json()
    assert set(bodega) == CAMPOS
    assert bodega["codigo"] == "ZZT-NORTE"
    assert bodega["nombre"] == "Bodega Norte"
    assert bodega["direccion"] == "Calle 80 # 10-20"
    assert bodega["estado"] == "ACTIVO"
    otra = cliente.get(f"/bodegas/{bodega['id_bodega']}", headers=CABECERAS)
    assert otra.get_json() == bodega


def test_codigo_se_recorta_y_pasa_a_mayusculas(cliente):
    respuesta = post(cliente, cuerpo(codigo="zzt-abc "))
    assert respuesta.get_json()["codigo"] == "ZZT-ABC"
    assert len(filas_con_codigo("ZZT-ABC")) == 1


def test_textos_se_recortan(cliente):
    bodega = post(cliente, cuerpo(nombre="  Norte  ", direccion=" Calle 1 ")).get_json()
    assert (bodega["nombre"], bodega["direccion"]) == ("Norte", "Calle 1")


@pytest.mark.parametrize("repetido", ["ZZT-NORTE", "zzt-norte", " Zzt-Norte "])
def test_codigo_duplicado_da_409(cliente, repetido):
    assert post(cliente, cuerpo()).status_code == 201
    error = verificar_error(
        post(cliente, cuerpo(codigo=repetido, nombre="Otra")), 409, "CODIGO_DUPLICADO")
    assert list(error["detalles"]) == ["codigo"]
    filas = filas_con_codigo("ZZT-NORTE")
    assert len(filas) == 1
    assert leer_sql(filas[0]["id_bodega"])["nombre"] == "Bodega Norte"


def test_codigo_de_30_caracteres_se_acepta(cliente):
    codigo = PREFIJO + "X" * (30 - len(PREFIJO))
    assert post(cliente, cuerpo(codigo=codigo)).status_code == 201


@pytest.mark.parametrize(
    "codigo",
    [QUITAR, None, "", "   ", PREFIJO + "X" * 27, "ZZT-A B", "ZZT-A/B", "ZZT-A.B", "ZZT-Ñ", 12],
)
def test_codigo_invalido_da_422(cliente, codigo):
    verificar_422(post(cliente, cuerpo(codigo=codigo)), "codigo")


@pytest.mark.parametrize("campo, largo_ok", [("nombre", 100), ("direccion", 255)])
def test_limites_de_texto(cliente, campo, largo_ok):
    assert post(cliente, cuerpo(**{campo: "x" * largo_ok})).status_code == 201
    verificar_422(
        post(cliente, cuerpo(codigo="ZZT-OTRA", **{campo: "x" * (largo_ok + 1)})), campo)


@pytest.mark.parametrize("campo", ["nombre", "direccion"])
@pytest.mark.parametrize("valor", [QUITAR, None, "", "   ", 5])
def test_nombre_y_direccion_obligatorios(cliente, campo, valor):
    verificar_422(post(cliente, cuerpo(**{campo: valor})), campo)


def test_varios_errores_juntos(cliente):
    verificar_422(post(cliente, cuerpo(codigo="MAL CODIGO", nombre="", direccion=None)),
                  "codigo", "nombre", "direccion")


def test_cuerpo_vacio_reporta_todos_los_obligatorios(cliente):
    verificar_422(post(cliente, {}), "codigo", "nombre", "direccion")


def test_texto_con_tildes_enie_y_comilla(cliente):
    texto = "ZZT O'Brien ñandú"
    bodega = post(cliente, cuerpo(nombre=texto, direccion=texto)).get_json()
    assert bodega["nombre"] == bodega["direccion"] == texto
    assert leer_sql(bodega["id_bodega"])["nombre"] == texto


@pytest.mark.parametrize("ronda", range(10))
def test_concurrencia_mismo_codigo(app, ronda):
    codigo = f"ZZT-CONC-{ronda}"
    barrera = threading.Barrier(2)
    resultados = []

    def crear():
        cliente = app.test_client()
        barrera.wait()
        resultados.append(post(cliente, cuerpo(codigo=codigo)).status_code)

    hilos = [threading.Thread(target=crear) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert sorted(resultados) == [201, 409]
    assert len(filas_con_codigo(codigo)) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"data": "codigo=ZZT-1", "content_type": "application/x-www-form-urlencoded"},
        {"data": "{no es json", "content_type": "application/json"},
        {"data": '["ZZT-1"]', "content_type": "application/json"},
        {},
    ],
)
def test_cuerpo_que_no_es_objeto_json_da_400(cliente, kwargs):
    respuesta = cliente.post("/bodegas", headers=CABECERAS, **kwargs)
    verificar_error(respuesta, 400, "PETICION_INVALIDA")


def test_post_sin_token_da_401(cliente):
    verificar_error(cliente.post("/bodegas", json=cuerpo()), 401, "NO_AUTENTICADO")
    assert filas_con_codigo("ZZT-NORTE") == []


def test_estado_y_campos_desconocidos_se_ignoran(cliente):
    respuesta = post(cliente, cuerpo(estado="INACTIVO", id_bodega=999, creado_en="2000-01-01"))
    assert respuesta.status_code == 201
    bodega = respuesta.get_json()
    assert bodega["estado"] == "ACTIVO"
    assert bodega["id_bodega"] != 999
    assert set(bodega) == CAMPOS


# --- PUT ----------------------------------------------------------------------


def test_put_cambia_nombre_y_direccion(cliente):
    id_bodega = crear_sql("SUR")
    respuesta = put(cliente, id_bodega, {"nombre": " Bodega Sur ", "direccion": "Av. 68 # 1-2"})
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "id_bodega": id_bodega,
        "codigo": "ZZT-SUR",
        "nombre": "Bodega Sur",
        "direccion": "Av. 68 # 1-2",
        "estado": "ACTIVO",
    }
    assert cliente.get(f"/bodegas/{id_bodega}", headers=CABECERAS).get_json() == respuesta.get_json()


def test_put_id_inexistente_da_404(cliente):
    error = verificar_error(put(cliente, 999_999_999, cuerpo()), 404, "NO_EXISTE")
    assert error["mensaje"] == "La bodega no existe."


@pytest.mark.parametrize("ruta", ["/bodegas/abc", "/bodegas/-1", "/bodegas/1.5"])
def test_put_id_no_entero_da_404(cliente, ruta):
    verificar_error(cliente.put(ruta, headers=CABECERAS, json=cuerpo()), 404, "NO_EXISTE")


@pytest.mark.parametrize("codigo", ["ZZT-OTRO", "MAL CODIGO /", None, 123])
def test_put_ignora_el_codigo(cliente, codigo):
    id_bodega = crear_sql("FIJO")
    respuesta = put(cliente, id_bodega, cuerpo(codigo=codigo))
    assert respuesta.status_code == 200
    assert respuesta.get_json()["codigo"] == "ZZT-FIJO"
    assert leer_sql(id_bodega)["codigo"] == "ZZT-FIJO"


@pytest.mark.parametrize("estado", ["INACTIVO", "BORRADA"])
def test_put_ignora_el_estado(cliente, estado):
    id_bodega = crear_sql("EST")
    assert put(cliente, id_bodega, cuerpo(estado=estado)).get_json()["estado"] == "ACTIVO"
    assert leer_sql(id_bodega)["estado"] == "ACTIVO"


def test_put_bodega_inactiva_sigue_inactiva(cliente):
    id_bodega = crear_sql("INACT", estado="INACTIVO")
    bodega = put(cliente, id_bodega, cuerpo(nombre="Renombrada", estado="ACTIVO")).get_json()
    assert bodega["nombre"] == "Renombrada"
    assert bodega["estado"] == "INACTIVO"


def test_put_valida_campos_juntos(cliente):
    id_bodega = crear_sql("VAL")
    verificar_422(put(cliente, id_bodega, {"nombre": "", "direccion": "x" * 256}),
                  "nombre", "direccion")
    assert leer_sql(id_bodega)["nombre"] == "Bodega original"


def test_put_cuerpo_invalido_con_id_inexistente_da_422(cliente):
    verificar_422(put(cliente, 999_999_999, {}), "nombre", "direccion")


def test_put_cuerpo_valido_con_id_inexistente_da_404(cliente):
    verificar_error(put(cliente, 999_999_999, cuerpo()), 404, "NO_EXISTE")


def test_put_cuerpo_no_json_da_400(cliente):
    id_bodega = crear_sql("JSON")
    respuesta = cliente.put(
        f"/bodegas/{id_bodega}", headers=CABECERAS, data="texto", content_type="text/plain")
    verificar_error(respuesta, 400, "PETICION_INVALIDA")


def test_put_sin_token_da_401(cliente):
    id_bodega = crear_sql("TOKEN")
    verificar_error(cliente.put(f"/bodegas/{id_bodega}", json=cuerpo()), 401, "NO_AUTENTICADO")
    assert leer_sql(id_bodega)["nombre"] == "Bodega original"
