"""Pool de conexiones MySQL y manejo transaccional con SQL parametrizado."""

from contextlib import contextmanager
from typing import Iterator

from flask import current_app
import mysql.connector
from mysql.connector import Error as MySQLError
from mysql.connector.pooling import MySQLConnectionPool, PooledMySQLConnection

from app.config import ConfigCompras
from app.errors import ErrorAPI

_pool: MySQLConnectionPool | None = None


def inicializar_pool(config: ConfigCompras) -> MySQLConnectionPool:
    """Inicializa el pool de conexiones MySQL en UTC y utf8mb4_0900_ai_ci."""
    global _pool
    _pool = MySQLConnectionPool(
        pool_name="ms_compras_pool",
        pool_size=config.db_pool_size,
        pool_reset_session=True,
        host=config.db_host,
        port=config.db_port,
        user=config.db_user,
        password=config.db_password,
        database=config.db_name,
        time_zone="+00:00",
        charset="utf8mb4",
        collation="utf8mb4_0900_ai_ci",
        autocommit=False,
    )
    return _pool


def obtener_pool() -> MySQLConnectionPool:
    """Obtiene el pool activo o lo inicializa de manera perezosa."""
    global _pool
    if _pool is None:
        config: ConfigCompras = current_app.config["COMPRAS_CONFIG"]
        try:
            _pool = inicializar_pool(config)
        except MySQLError as exc:
            raise ErrorAPI(
                503,
                "SERVICIO_NO_DISPONIBLE",
                "Base de datos de compras no disponible.",
                {"detalle": str(exc)},
            ) from exc
    return _pool


@contextmanager
def obtener_conexion() -> Iterator[tuple[PooledMySQLConnection, object]]:
    """Entrega conexion y cursor de diccionario para consultas de lectura."""
    try:
        conexion = obtener_pool().get_connection()
    except MySQLError as exc:
        raise ErrorAPI(
            503,
            "SERVICIO_NO_DISPONIBLE",
            "No fue posible conectar con la base de datos de compras.",
            {"detalle": str(exc)},
        ) from exc

    cursor = conexion.cursor(dictionary=True)
    try:
        yield conexion, cursor
    except MySQLError as exc:
        raise ErrorAPI(
            503,
            "SERVICIO_NO_DISPONIBLE",
            "Error al consultar la base de datos de compras.",
            {"detalle": str(exc)},
        ) from exc
    finally:
        cursor.close()
        conexion.close()


@contextmanager
def transaccion() -> Iterator[tuple[PooledMySQLConnection, object]]:
    """Abre una transaccion SQL explicita con rollback automatico ante cualquier error."""
    try:
        conexion = obtener_pool().get_connection()
    except MySQLError as exc:
        raise ErrorAPI(
            503,
            "SERVICIO_NO_DISPONIBLE",
            "No fue posible abrir transaccion en la base de datos de compras.",
            {"detalle": str(exc)},
        ) from exc

    cursor = conexion.cursor(dictionary=True)
    try:
        conexion.start_transaction()
        yield conexion, cursor
        conexion.commit()
    except ErrorAPI:
        conexion.rollback()
        raise
    except MySQLError as exc:
        conexion.rollback()
        raise ErrorAPI(
            503,
            "SERVICIO_NO_DISPONIBLE",
            "Error transaccional en la base de datos de compras.",
            {"detalle": str(exc)},
        ) from exc
    except Exception:
        conexion.rollback()
        raise
    finally:
        cursor.close()
        conexion.close()


def verificar_salud_db() -> None:
    """Comprueba conectividad real con MySQL mediante SELECT 1."""
    with obtener_conexion() as (_conexion, cursor):
        cursor.execute("SELECT 1 AS ok")
        cursor.fetchone()
