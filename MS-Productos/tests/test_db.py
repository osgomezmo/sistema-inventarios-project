"""Pruebas de la capa de datos contra el MySQL de desarrollo (127.0.0.1:33061).

Cada prueba que escribe datos corre en una transacción que siempre se revierte.
Si MySQL no está disponible, esas pruebas se saltan.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import mysql.connector
import pytest

from app import create_app
from app.config import cargar_configuracion
from app.db import MENSAJE_SIN_BASE, abrir_conexion, transaccion
from app.errors import ApiError
from db.aplicar_migraciones import CARPETA, aplicar, sentencias

CONFIG = cargar_configuracion()
CONFIG_PUERTO_CERRADO = {
    "DB_HOST": "127.0.0.1",
    "DB_PORT": 1,
    "DB_USER": "usuario-de-prueba",
    "DB_PASSWORD": "clave-de-prueba",
    "DB_NAME": "base-de-prueba",
}


@pytest.fixture(scope="session")
def config_mysql():
    try:
        abrir_conexion(CONFIG).close()
    except ApiError:
        pytest.skip("MySQL de desarrollo no disponible en 127.0.0.1:33061")
    aplicar(CONFIG)
    return CONFIG


@pytest.fixture
def cursor(config_mysql):
    conexion = abrir_conexion(config_mysql)
    conexion.start_transaction()
    cur = conexion.cursor(dictionary=True)
    try:
        yield cur
    finally:
        cur.close()
        conexion.rollback()
        conexion.close()


def crear_categoria(cursor, nombre, id_padre=None):
    cursor.execute(
        "INSERT INTO categorias (nombre, descripcion, id_categoria_padre) VALUES (%s, %s, %s)",
        (nombre, f"Descripción de {nombre}", id_padre),
    )
    return cursor.lastrowid


def crear_producto(cursor, sku, id_categoria, precio="4250.50", stock_minimo="12.345"):
    cursor.execute(
        "INSERT INTO productos (sku, nombre, descripcion, marca, id_categoria,"
        " unidad_medida, precio_venta, stock_minimo)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (sku, "Leche entera 1 L", None, "Alquería", id_categoria, "UNIDAD",
         Decimal(precio), Decimal(stock_minimo)),
    )
    return cursor.lastrowid


def leer(cursor, tabla, columna_id, valor):
    # Tabla y columna son constantes de la prueba; el valor va parametrizado.
    cursor.execute(f"SELECT * FROM {tabla} WHERE {columna_id} = %s", (valor,))
    return cursor.fetchone()


# --- Sin base de datos ---------------------------------------------------------


def test_el_script_001_tiene_dos_sentencias_sin_comentarios():
    partes = sentencias((CARPETA / "001_categorias_productos.sql").read_text(encoding="utf-8"))
    assert len(partes) == 2
    assert all(p.startswith("CREATE TABLE IF NOT EXISTS") for p in partes)
    assert not any("--" in p for p in partes)


def test_conexion_fallida_responde_503_sin_revelar_credenciales():
    with pytest.raises(ApiError) as info:
        abrir_conexion(CONFIG_PUERTO_CERRADO)

    error = info.value
    assert (error.status, error.codigo, error.mensaje) == (
        503, "SERVICIO_NO_DISPONIBLE", MENSAJE_SIN_BASE)
    assert error.__cause__ is None and error.__suppress_context__
    texto = f"{error} {error.mensaje} {error.detalles}"
    for dato in ("127.0.0.1", "usuario-de-prueba", "clave-de-prueba", "base-de-prueba"):
        assert dato not in texto


def test_sin_base_la_api_responde_503_en_json():
    app = create_app({"TESTING": True, "SERVICE_TOKEN": "token-de-prueba", **CONFIG_PUERTO_CERRADO})

    @app.get("/prueba-db")
    def prueba_db():
        with transaccion():
            return {"ok": True}

    respuesta = app.test_client().get(
        "/prueba-db", headers={"Authorization": "Bearer token-de-prueba"})
    assert respuesta.status_code == 503
    assert respuesta.get_json()["error"]["codigo"] == "SERVICIO_NO_DISPONIBLE"
    assert b"usuario-de-prueba" not in respuesta.data
    assert b"clave-de-prueba" not in respuesta.data


# --- Con MySQL de desarrollo -------------------------------------------------------


def test_aplicador_deja_las_tablas_y_es_idempotente(config_mysql):
    assert aplicar(config_mysql) == []
    assert aplicar(config_mysql) == []

    with transaccion(config_mysql) as cur:
        cur.execute(
            "SELECT TABLE_NAME AS tabla FROM information_schema.TABLES"
            " WHERE TABLE_SCHEMA = DATABASE()"
        )
        tablas = {fila["tabla"] for fila in cur.fetchall()}
        cur.execute("SELECT nombre FROM migraciones_aplicadas")
        aplicadas = [fila["nombre"] for fila in cur.fetchall()]

    assert {"categorias", "productos", "migraciones_aplicadas"} <= tablas
    assert aplicadas.count("001_categorias_productos.sql") == 1


def test_sesion_en_utc(cursor):
    cursor.execute("SELECT @@session.time_zone AS zona")
    assert cursor.fetchone()["zona"] == "+00:00"


def test_crea_categoria_subcategoria_y_producto(cursor):
    id_raiz = crear_categoria(cursor, "Lácteos de prueba")
    id_sub = crear_categoria(cursor, "Leches de prueba", id_raiz)
    id_producto = crear_producto(cursor, "PRB-0001", id_sub)

    raiz = leer(cursor, "categorias", "id_categoria", id_raiz)
    sub = leer(cursor, "categorias", "id_categoria", id_sub)
    producto = leer(cursor, "productos", "id_producto", id_producto)

    assert raiz["id_categoria_padre"] is None and raiz["estado"] == "ACTIVO"
    assert sub["id_categoria_padre"] == id_raiz
    assert producto["sku"] == "PRB-0001"
    assert producto["id_categoria"] == id_sub
    assert producto["unidad_medida"] == "UNIDAD"
    assert producto["estado"] == "ACTIVO"


def test_sku_duplicado_falla(cursor):
    id_categoria = crear_categoria(cursor, "Categoría SKU duplicado")
    crear_producto(cursor, "PRB-DUP", id_categoria)

    with pytest.raises(mysql.connector.IntegrityError) as info:
        crear_producto(cursor, "PRB-DUP", id_categoria)
    assert info.value.errno == 1062


def test_producto_con_categoria_inexistente_falla(cursor):
    with pytest.raises(mysql.connector.IntegrityError) as info:
        crear_producto(cursor, "PRB-SIN-CAT", 999_999_999)
    assert info.value.errno == 1452


def test_decimales_se_conservan(cursor):
    id_categoria = crear_categoria(cursor, "Categoría decimales")
    id_producto = crear_producto(cursor, "PRB-DEC", id_categoria, "4250.50", "12.345")

    producto = leer(cursor, "productos", "id_producto", id_producto)
    assert isinstance(producto["precio_venta"], Decimal)
    assert isinstance(producto["stock_minimo"], Decimal)
    assert producto["precio_venta"] == Decimal("4250.50")
    assert producto["stock_minimo"] == Decimal("12.345")


def test_creado_en_es_datetime_en_utc(cursor):
    id_categoria = crear_categoria(cursor, "Categoría fecha")
    creado_en = leer(cursor, "categorias", "id_categoria", id_categoria)["creado_en"]

    assert isinstance(creado_en, datetime)
    assert creado_en.tzinfo is None
    ahora_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs(ahora_utc - creado_en) < timedelta(minutes=1)


def test_valor_con_comilla_funciona_con_parametros(cursor):
    nombre = "O'Brien'; DROP TABLE productos; --"
    id_categoria = crear_categoria(cursor, nombre)

    cursor.execute("SELECT id_categoria FROM categorias WHERE nombre = %s", (nombre,))
    assert cursor.fetchone()["id_categoria"] == id_categoria
    cursor.execute("SELECT COUNT(*) AS n FROM productos")
    assert cursor.fetchone()["n"] >= 0


def test_transaccion_revierte_si_hay_excepcion(config_mysql):
    nombre = "Categoría que no debe quedar"
    with pytest.raises(RuntimeError):
        with transaccion(config_mysql) as cur:
            cur.execute("INSERT INTO categorias (nombre) VALUES (%s)", (nombre,))
            raise RuntimeError("falla a propósito")

    with transaccion(config_mysql) as cur:
        cur.execute("SELECT COUNT(*) AS n FROM categorias WHERE nombre = %s", (nombre,))
        assert cur.fetchone()["n"] == 0


def test_credenciales_invalidas_responden_503_sin_revelarlas(config_mysql):
    config = {**config_mysql, "DB_USER": "usuario-inexistente", "DB_PASSWORD": "clave-falsa"}
    with pytest.raises(ApiError) as info:
        abrir_conexion(config)

    error = info.value
    assert error.status == 503 and error.__cause__ is None
    texto = f"{error} {error.mensaje} {error.detalles}"
    assert "usuario-inexistente" not in texto and "clave-falsa" not in texto
