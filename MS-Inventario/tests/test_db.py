"""Pruebas de la capa de datos contra el MySQL de desarrollo (127.0.0.1:33062).

Cada prueba que escribe datos corre en una transacción que siempre se revierte.
Los códigos de bodega usan el prefijo "ZZT-" y los SKU "ZZTEST-". Si MySQL no
está disponible, esas pruebas se saltan.
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
TABLAS = {"bodegas", "saldos", "traslados", "movimientos", "eventos_procesados"}
ERROR_DUPLICADO = 1062
ERROR_FK = 1452
ERROR_CHECK = 3819
ERROR_ENUM = 1265


@pytest.fixture(scope="session")
def config_mysql():
    try:
        abrir_conexion(CONFIG).close()
    except ApiError:
        pytest.skip("MySQL de desarrollo no disponible en 127.0.0.1:33062")
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


def crear_bodega(cursor, codigo="ZZT-B1", nombre="Bodega de prueba"):
    cursor.execute(
        "INSERT INTO bodegas (codigo, nombre, direccion) VALUES (%s, %s, %s)",
        (codigo, nombre, "Calle 1 # 2-3"),
    )
    return cursor.lastrowid


def crear_saldo(cursor, id_bodega, sku="ZZTEST-001", cantidad="10.000",
                costo="3150.1234", minimo="2.000"):
    cursor.execute(
        "INSERT INTO saldos (sku, id_bodega, cantidad, costo_promedio, stock_minimo)"
        " VALUES (%s, %s, %s, %s, %s)",
        (sku, id_bodega, Decimal(cantidad), Decimal(costo), Decimal(minimo)),
    )
    return cursor.lastrowid


def crear_movimiento(cursor, id_bodega, sku="ZZTEST-001", tipo="AJUSTE_POSITIVO",
                     cantidad="5.125", costo="3150.1234", saldo="5.125",
                     promedio="3150.1234", valor="16144.38", id_traslado=None):
    cursor.execute(
        "INSERT INTO movimientos (sku, id_bodega, tipo, cantidad, costo_unitario,"
        " saldo_resultante, costo_promedio, valor_resultante, motivo,"
        " documento_referencia, id_usuario, id_traslado)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (sku, id_bodega, tipo, Decimal(cantidad), Decimal(costo), Decimal(saldo),
         Decimal(promedio), Decimal(valor), "Conteo inicial", None, 7, id_traslado),
    )
    return cursor.lastrowid


def crear_traslado(cursor, origen, destino, cantidad="1.000"):
    cursor.execute(
        "INSERT INTO traslados (sku, id_bodega_origen, id_bodega_destino, cantidad,"
        " motivo, id_usuario) VALUES (%s, %s, %s, %s, %s, %s)",
        ("ZZTEST-001", origen, destino, Decimal(cantidad), "Reposición", 7),
    )
    return cursor.lastrowid


def leer(cursor, tabla, columna_id, valor):
    # Tabla y columna son constantes de la prueba; el valor va parametrizado.
    cursor.execute(f"SELECT * FROM {tabla} WHERE {columna_id} = %s", (valor,))
    return cursor.fetchone()


def errno_de(funcion):
    with pytest.raises(mysql.connector.Error) as info:
        funcion()
    return info.value.errno


# --- Sin base de datos ---------------------------------------------------------


def test_el_script_001_tiene_cinco_sentencias():
    texto = (CARPETA / "001_bodegas_saldos_movimientos.sql").read_text(encoding="utf-8")
    partes = sentencias(texto)
    assert len(partes) == 5
    assert all(p.startswith("CREATE TABLE IF NOT EXISTS") for p in partes)
    assert all(p.count("(") == p.count(")") for p in partes)
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

    assert TABLAS | {"migraciones_aplicadas"} <= tablas
    assert aplicadas.count("001_bodegas_saldos_movimientos.sql") == 1


def test_sesion_en_utc(cursor):
    cursor.execute("SELECT @@session.time_zone AS zona")
    assert cursor.fetchone()["zona"] == "+00:00"


def test_crea_bodega_saldo_y_movimiento(cursor):
    id_bodega = crear_bodega(cursor)
    id_saldo = crear_saldo(cursor, id_bodega)
    id_movimiento = crear_movimiento(cursor, id_bodega)

    bodega = leer(cursor, "bodegas", "id_bodega", id_bodega)
    saldo = leer(cursor, "saldos", "id_saldo", id_saldo)
    movimiento = leer(cursor, "movimientos", "id_movimiento", id_movimiento)

    assert bodega["codigo"] == "ZZT-B1" and bodega["estado"] == "ACTIVO"
    assert saldo["sku"] == "ZZTEST-001" and saldo["id_bodega"] == id_bodega
    assert movimiento["tipo"] == "AJUSTE_POSITIVO"
    assert movimiento["id_usuario"] == 7
    assert movimiento["id_traslado"] is None


def test_crea_traslado_con_sus_movimientos(cursor):
    origen = crear_bodega(cursor, "ZZT-O")
    destino = crear_bodega(cursor, "ZZT-D")
    id_traslado = crear_traslado(cursor, origen, destino)
    salida = crear_movimiento(cursor, origen, tipo="TRASLADO_SALIDA", id_traslado=id_traslado)
    entrada = crear_movimiento(cursor, destino, tipo="TRASLADO_ENTRADA", id_traslado=id_traslado)

    cursor.execute(
        "SELECT id_movimiento FROM movimientos WHERE id_traslado = %s ORDER BY id_movimiento",
        (id_traslado,),
    )
    assert [f["id_movimiento"] for f in cursor.fetchall()] == [salida, entrada]


def test_codigo_de_bodega_duplicado_falla(cursor):
    crear_bodega(cursor, "ZZT-DUP")
    assert errno_de(lambda: crear_bodega(cursor, "ZZT-DUP", "Otra")) == ERROR_DUPLICADO


def test_saldo_unico_por_sku_y_bodega(cursor):
    id_bodega = crear_bodega(cursor)
    crear_saldo(cursor, id_bodega)
    assert errno_de(lambda: crear_saldo(cursor, id_bodega)) == ERROR_DUPLICADO
    # El mismo SKU en otra bodega sí se permite.
    crear_saldo(cursor, crear_bodega(cursor, "ZZT-B2"))


def test_check_rechaza_saldo_negativo(cursor):
    id_bodega = crear_bodega(cursor)
    assert errno_de(lambda: crear_saldo(cursor, id_bodega, cantidad="-0.001")) == ERROR_CHECK
    id_saldo = crear_saldo(cursor, id_bodega)
    actualizar = lambda: cursor.execute(  # noqa: E731
        "UPDATE saldos SET cantidad = cantidad - %s WHERE id_saldo = %s",
        (Decimal("10.001"), id_saldo),
    )
    assert errno_de(actualizar) == ERROR_CHECK


def test_check_rechaza_costo_promedio_negativo(cursor):
    id_bodega = crear_bodega(cursor)
    assert errno_de(lambda: crear_saldo(cursor, id_bodega, costo="-1")) == ERROR_CHECK


@pytest.mark.parametrize("cantidad", ["0", "-1.500"])
def test_check_rechaza_movimiento_sin_cantidad_positiva(cursor, cantidad):
    id_bodega = crear_bodega(cursor)
    assert errno_de(lambda: crear_movimiento(cursor, id_bodega, cantidad=cantidad)) == ERROR_CHECK


def test_check_rechaza_traslado_a_la_misma_bodega(cursor):
    id_bodega = crear_bodega(cursor)
    assert errno_de(lambda: crear_traslado(cursor, id_bodega, id_bodega)) == ERROR_CHECK


def test_check_rechaza_traslado_sin_cantidad_positiva(cursor):
    origen = crear_bodega(cursor, "ZZT-O")
    destino = crear_bodega(cursor, "ZZT-D")
    assert errno_de(lambda: crear_traslado(cursor, origen, destino, "0")) == ERROR_CHECK


def test_tipo_fuera_del_enum_es_rechazado(cursor):
    id_bodega = crear_bodega(cursor)
    assert errno_de(lambda: crear_movimiento(cursor, id_bodega, tipo="REGALO")) == ERROR_ENUM


@pytest.mark.parametrize("tabla", ["saldos", "movimientos", "traslados_origen", "traslados_destino"])
def test_fk_rechaza_bodega_inexistente(cursor, tabla):
    id_bodega = crear_bodega(cursor)
    inexistente = 999_999_999
    acciones = {
        "saldos": lambda: crear_saldo(cursor, inexistente),
        "movimientos": lambda: crear_movimiento(cursor, inexistente),
        "traslados_origen": lambda: crear_traslado(cursor, inexistente, id_bodega),
        "traslados_destino": lambda: crear_traslado(cursor, id_bodega, inexistente),
    }
    assert errno_de(acciones[tabla]) == ERROR_FK


def test_fk_rechaza_traslado_inexistente(cursor):
    id_bodega = crear_bodega(cursor)
    assert errno_de(lambda: crear_movimiento(cursor, id_bodega, id_traslado=999_999_999)) == ERROR_FK


def test_decimales_se_conservan_exactos(cursor):
    id_bodega = crear_bodega(cursor)
    id_saldo = crear_saldo(cursor, id_bodega, cantidad="12.345", costo="3150.0001", minimo="0.125")
    id_movimiento = crear_movimiento(
        cursor, id_bodega, cantidad="0.001", costo="9999999999.9999", saldo="12.345",
        promedio="3150.0001", valor="1234567890123456.78")

    saldo = leer(cursor, "saldos", "id_saldo", id_saldo)
    movimiento = leer(cursor, "movimientos", "id_movimiento", id_movimiento)
    assert saldo["cantidad"] == Decimal("12.345")
    assert saldo["costo_promedio"] == Decimal("3150.0001")
    assert saldo["stock_minimo"] == Decimal("0.125")
    assert movimiento["cantidad"] == Decimal("0.001")
    assert movimiento["costo_unitario"] == Decimal("9999999999.9999")
    assert movimiento["valor_resultante"] == Decimal("1234567890123456.78")
    for valor in (saldo["cantidad"], movimiento["costo_unitario"], movimiento["valor_resultante"]):
        assert isinstance(valor, Decimal)


def test_fechas_son_datetime_en_utc(cursor):
    id_bodega = crear_bodega(cursor)
    id_saldo = crear_saldo(cursor, id_bodega)
    id_movimiento = crear_movimiento(cursor, id_bodega)
    cursor.execute(
        "INSERT INTO eventos_procesados (id_evento, tipo) VALUES (%s, %s)",
        ("6f1c2a9e-1b7d-4c55-9a51-3f0e8d2b7c10", "MercanciaRecibida"),
    )

    fechas = [
        leer(cursor, "bodegas", "id_bodega", id_bodega)["creado_en"],
        leer(cursor, "saldos", "id_saldo", id_saldo)["actualizado_en"],
        leer(cursor, "movimientos", "id_movimiento", id_movimiento)["fecha"],
        leer(cursor, "eventos_procesados", "id_evento",
             "6f1c2a9e-1b7d-4c55-9a51-3f0e8d2b7c10")["procesado_en"],
    ]
    ahora_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    for fecha in fechas:
        assert isinstance(fecha, datetime) and fecha.tzinfo is None
        assert abs(ahora_utc - fecha) < timedelta(minutes=1)


def test_evento_procesado_no_se_repite(cursor):
    insertar = lambda: cursor.execute(  # noqa: E731
        "INSERT INTO eventos_procesados (id_evento, tipo) VALUES (%s, %s)",
        ("c1f4b8e2-77a0-4d1e-9a3b-0c5d6e7f8a90", "MercanciaRecibida"),
    )
    insertar()
    assert errno_de(insertar) == ERROR_DUPLICADO


def test_valor_con_comilla_funciona_con_parametros(cursor):
    sku = "ZZTEST-O'Brien'; DROP TABLE saldos; --"
    id_bodega = crear_bodega(cursor)
    crear_saldo(cursor, id_bodega, sku=sku)

    cursor.execute("SELECT sku FROM saldos WHERE sku = %s", (sku,))
    assert cursor.fetchone()["sku"] == sku
    # La tabla sigue existiendo: el texto se trató como dato, no como SQL.
    cursor.execute("SELECT COUNT(*) AS n FROM saldos WHERE id_bodega = %s", (id_bodega,))
    assert cursor.fetchone()["n"] == 1


def test_transaccion_revierte_si_hay_excepcion(config_mysql):
    with pytest.raises(RuntimeError):
        with transaccion(config_mysql) as cur:
            crear_bodega(cur, "ZZT-REVERTIDA")
            raise RuntimeError("falla a propósito")

    with transaccion(config_mysql) as cur:
        cur.execute("SELECT COUNT(*) AS n FROM bodegas WHERE codigo = %s", ("ZZT-REVERTIDA",))
        assert cur.fetchone()["n"] == 0


def test_credenciales_invalidas_responden_503_sin_revelarlas(config_mysql):
    config = {**config_mysql, "DB_USER": "usuario-inexistente", "DB_PASSWORD": "clave-falsa"}
    with pytest.raises(ApiError) as info:
        abrir_conexion(config)

    error = info.value
    assert error.status == 503 and error.__cause__ is None
    texto = f"{error} {error.mensaje} {error.detalles}"
    assert "usuario-inexistente" not in texto and "clave-falsa" not in texto
