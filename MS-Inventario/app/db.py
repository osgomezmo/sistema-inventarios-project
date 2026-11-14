"""Acceso a MySQL con mysql-connector-python y SQL directo.

Se abre una conexión por petición. Todas las consultas deben ir
parametrizadas con %s; nunca se concatenan valores dentro del SQL.
"""

import logging
from contextlib import contextmanager

import mysql.connector
from flask import current_app

from app.errors import ApiError

MENSAJE_SIN_BASE = "La base de datos no está disponible."
registro = logging.getLogger(__name__)


def _configuracion(config):
    return config if config is not None else current_app.config


def abrir_conexion(config=None):
    """Abre una conexión nueva con la sesión en UTC y autocommit apagado.

    `config` es un diccionario con DB_HOST, DB_PORT, DB_USER, DB_PASSWORD y
    DB_NAME; si no se pasa, se toma de la aplicación Flask activa.
    """
    cfg = _configuracion(config)
    try:
        return mysql.connector.connect(
            host=cfg["DB_HOST"],
            port=int(cfg["DB_PORT"]),
            user=cfg["DB_USER"],
            password=cfg["DB_PASSWORD"],
            database=cfg["DB_NAME"],
            charset="utf8mb4",
            collation="utf8mb4_0900_ai_ci",
            time_zone="+00:00",
            autocommit=False,
            connection_timeout=5,
        )
    except mysql.connector.Error:
        # El error original incluye host y usuario: no se encadena ni se muestra.
        raise ApiError("SERVICIO_NO_DISPONIBLE", MENSAJE_SIN_BASE, 503) from None


@contextmanager
def transaccion(config=None):
    """Entrega un cursor de diccionarios dentro de una transacción.

    Hace commit si el bloque termina bien y rollback si lanza una excepción.
    El cursor y la conexión se cierran siempre.
    """
    conexion = abrir_conexion(config)
    cursor = None
    try:
        conexion.start_transaction()
        cursor = conexion.cursor(dictionary=True)
        yield cursor
        conexion.commit()
    except BaseException:
        try:
            conexion.rollback()
        except mysql.connector.Error:
            # Si la conexión se cayó, MySQL descarta la transacción por su cuenta;
            # se conserva la excepción original.
            pass
        raise
    finally:
        if cursor is not None:
            cursor.close()
        conexion.close()


ERROR_INTERBLOQUEO = 1213
ERROR_ESPERA_BLOQUEO = 1205


def _conflicto():
    return ApiError("CONFLICTO", "La operación coincidió con otra; intenta de nuevo.", 409)


def ejecutar_con_reintento(funcion):
    """Ejecuta `funcion` (que abre y cierra su propia transacción) y la repite
    una vez completa si MySQL la elige como víctima de un interbloqueo.

    Un segundo interbloqueo o una espera de bloqueo agotada responden 409
    CONFLICTO. Cualquier otro error se propaga igual.
    """
    for intento in (1, 2):
        try:
            return funcion()
        except mysql.connector.Error as error:
            if error.errno == ERROR_INTERBLOQUEO and intento == 1:
                registro.warning("Interbloqueo en MySQL; se repite la transacción.")
                continue
            if error.errno in (ERROR_INTERBLOQUEO, ERROR_ESPERA_BLOQUEO):
                raise _conflicto() from None
            raise
