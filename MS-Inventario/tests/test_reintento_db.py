"""Pruebas de ejecutar_con_reintento (D42). No necesitan MySQL."""

import mysql.connector
import pytest

from app.db import ejecutar_con_reintento
from app.errors import ApiError


def error_mysql(errno):
    return mysql.connector.errors.DatabaseError(msg=f"error {errno}", errno=errno)


class Funcion:
    """Lanza los errores indicados en orden y luego devuelve "ok"."""

    def __init__(self, *errores):
        self.errores = list(errores)
        self.llamadas = 0

    def __call__(self):
        self.llamadas += 1
        if self.errores:
            raise self.errores.pop(0)
        return "ok"


def test_sin_errores_se_ejecuta_una_vez():
    funcion = Funcion()
    assert ejecutar_con_reintento(funcion) == "ok"
    assert funcion.llamadas == 1


def test_interbloqueo_una_vez_se_repite_y_devuelve_el_valor():
    funcion = Funcion(error_mysql(1213))
    assert ejecutar_con_reintento(funcion) == "ok"
    assert funcion.llamadas == 2


def test_interbloqueo_dos_veces_da_conflicto():
    funcion = Funcion(error_mysql(1213), error_mysql(1213))
    with pytest.raises(ApiError) as info:
        ejecutar_con_reintento(funcion)
    assert (info.value.status, info.value.codigo) == (409, "CONFLICTO")
    assert info.value.mensaje == "La operación coincidió con otra; intenta de nuevo."
    assert info.value.__cause__ is None
    assert funcion.llamadas == 2


def test_espera_de_bloqueo_da_conflicto_sin_repetir():
    funcion = Funcion(error_mysql(1205))
    with pytest.raises(ApiError) as info:
        ejecutar_con_reintento(funcion)
    assert (info.value.status, info.value.codigo) == (409, "CONFLICTO")
    assert funcion.llamadas == 1


@pytest.mark.parametrize(
    "error",
    [
        error_mysql(1062),
        error_mysql(3819),
        ValueError("otro error"),
        ApiError("STOCK_INSUFICIENTE", "No hay saldo.", 409),
    ],
)
def test_otros_errores_se_propagan_sin_repetir(error):
    funcion = Funcion(error)
    with pytest.raises(type(error)) as info:
        ejecutar_con_reintento(funcion)
    assert info.value is error
    assert funcion.llamadas == 1
