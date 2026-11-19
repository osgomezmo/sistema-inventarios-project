"""Validación de entradas y parámetros query para MS-Reportes."""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.errors import ApiError

MENSAJE_VALIDACION = "Revisa los campos enviados."
MAX_INT32 = 2_147_483_647
_PATRON_ENTERO = re.compile(r"^-?\d+$")


class Errores:
    def __init__(self):
        self.detalles = {}

    def agregar(self, campo, mensaje):
        self.detalles.setdefault(campo, []).append(mensaje)

    def __bool__(self):
        return bool(self.detalles)

    def lanzar_si_hay(self):
        if self.detalles:
            raise ApiError("VALIDACION", MENSAJE_VALIDACION, 422, self.detalles)


def entero_opcional(errores, datos, campo, minimo=None, maximo=MAX_INT32):
    valor = datos.get(campo)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    if isinstance(valor, bool):
        errores.agregar(campo, "Debe ser un número entero.")
        return None
    if isinstance(valor, str):
        limpio = valor.strip()
        if not _PATRON_ENTERO.match(limpio):
            errores.agregar(campo, "Debe ser un número entero.")
            return None
        numero = int(limpio)
    elif isinstance(valor, int):
        numero = valor
    else:
        errores.agregar(campo, "Debe ser un número entero.")
        return None

    if minimo is not None and numero < minimo:
        errores.agregar(campo, f"Debe ser mayor o igual a {minimo}.")
    if maximo is not None and numero > maximo:
        errores.agregar(campo, f"Debe ser menor o igual a {maximo}.")
    return numero


def opcion(errores, datos, campo, opciones, obligatorio=False):
    valor = datos.get(campo)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if obligatorio:
            errores.agregar(campo, "Es obligatorio.")
        return None

    valor = str(valor).strip().lower()
    opciones_norm = [o.lower() for o in opciones]
    if valor not in opciones_norm:
        errores.agregar(campo, f"Debe ser una de: {', '.join(opciones)}.")
        return None
    return valor


def fecha_opcional(errores, datos, campo):
    valor = datos.get(campo)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None

    valor = str(valor).strip()
    try:
        fecha_obj = datetime.strptime(valor, "%Y-%m-%d").date()
        return fecha_obj.isoformat()
    except ValueError:
        errores.agregar(campo, "Formato inválido; use AAAA-MM-DD.")
        return None
