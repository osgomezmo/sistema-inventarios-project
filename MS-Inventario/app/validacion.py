"""Validación de entradas con errores acumulados por campo.

Las funciones reciben un objeto `Errores`, agregan los mensajes del campo que
revisan y devuelven el valor ya normalizado. Al final se llama a
`errores.lanzar_si_hay()`, que responde 422 con todos los campos a la vez.
"""

import re
from decimal import Decimal, InvalidOperation

from flask import request

from app.errors import ApiError

MENSAJE_VALIDACION = "Revisa los campos enviados."
PATRON_ENTERO = re.compile(r"-?\d+")
PATRON_DECIMAL = re.compile(r"-?\d+(\.\d+)?")
PATRON_SKU = re.compile(r"[A-Z0-9._-]+")
PATRON_CODIGO_BODEGA = re.compile(r"[A-Z0-9_-]+")


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


def leer_json():
    """Devuelve el cuerpo JSON como diccionario; si no lo es, 400."""
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise ApiError(
            "PETICION_INVALIDA", "El cuerpo debe ser un objeto JSON.", 400
        )
    return datos


def texto_obligatorio(errores, datos, campo, maximo):
    valor = datos.get(campo)
    if valor is None:
        errores.agregar(campo, "Es obligatorio.")
        return None
    if not isinstance(valor, str):
        errores.agregar(campo, "Debe ser texto.")
        return None
    valor = valor.strip()
    if not valor:
        errores.agregar(campo, "Es obligatorio.")
        return None
    if len(valor) > maximo:
        errores.agregar(campo, f"Máximo {maximo} caracteres.")
        return None
    return valor


def texto_opcional(errores, datos, campo, maximo):
    """Texto que puede faltar o venir vacío; en ese caso devuelve None."""
    valor = datos.get(campo)
    if valor is None:
        return None
    if not isinstance(valor, str):
        errores.agregar(campo, "Debe ser texto.")
        return None
    valor = valor.strip()
    if not valor:
        return None
    if len(valor) > maximo:
        errores.agregar(campo, f"Máximo {maximo} caracteres.")
        return None
    return valor


def entero_opcional(errores, datos, campo, minimo=None, maximo=None):
    """Entero de JSON o de la query string. Acepta 5 y "5"; rechaza 5.0 y true."""
    valor = datos.get(campo)
    if valor is None or valor == "":
        return None
    if isinstance(valor, bool):
        numero = None
    elif isinstance(valor, int):
        numero = valor
    elif isinstance(valor, str) and PATRON_ENTERO.fullmatch(valor.strip()):
        numero = int(valor.strip())
    else:
        numero = None

    if numero is None:
        errores.agregar(campo, "Debe ser un número entero.")
        return None
    if minimo is not None and numero < minimo:
        errores.agregar(campo, f"Debe ser mayor o igual a {minimo}.")
        return None
    if maximo is not None and numero > maximo:
        errores.agregar(campo, f"Debe ser menor o igual a {maximo}.")
        return None
    return numero


def opcion(errores, datos, campo, opciones, obligatorio=False):
    """Valor que debe estar en `opciones` (por ejemplo, el estado)."""
    valor = datos.get(campo)
    if valor is None or valor == "":
        if obligatorio:
            errores.agregar(campo, "Es obligatorio.")
        return None
    if valor not in opciones:
        errores.agregar(campo, f"Debe ser uno de: {', '.join(opciones)}.")
        return None
    return valor


def decimal_opcional(errores, datos, campo, minimo=None, decimales=None, maximo=None):
    """Número decimal de JSON o de la query string, devuelto como Decimal.

    Acepta 12, 12.5 y "12.50"; rechaza true, "abc", "nan", "inf" y la notación
    científica. Si se indica `decimales`, no admite más cifras decimales.
    """
    valor = datos.get(campo)
    if valor is None or valor == "":
        return None
    numero = None
    if isinstance(valor, bool):
        numero = None
    elif isinstance(valor, (int, float)):
        try:
            numero = Decimal(str(valor))
        except InvalidOperation:
            numero = None
    elif isinstance(valor, str) and PATRON_DECIMAL.fullmatch(valor.strip()):
        numero = Decimal(valor.strip())

    if numero is None or not numero.is_finite():
        errores.agregar(campo, "Debe ser un número.")
        return None
    if minimo is not None and numero < minimo:
        errores.agregar(campo, f"Debe ser mayor o igual a {minimo}.")
        return None
    if maximo is not None and numero > maximo:
        errores.agregar(campo, f"Debe ser menor o igual a {maximo}.")
        return None
    if decimales is not None and -numero.as_tuple().exponent > decimales:
        errores.agregar(campo, f"Máximo {decimales} decimales.")
        return None
    return numero


def lista_separada_por_comas(errores, datos, campo, max_elementos, max_largo):
    """Lista "a, b,,c" -> ["a", "b", "c"]. None si el campo no viene."""
    valor = datos.get(campo)
    if valor is None:
        return None
    if not isinstance(valor, str):
        errores.agregar(campo, "Debe ser una lista separada por comas.")
        return None
    elementos = [parte.strip() for parte in valor.split(",") if parte.strip()]
    if len(elementos) > max_elementos:
        errores.agregar(campo, f"Máximo {max_elementos} elementos.")
        return None
    if any(len(e) > max_largo for e in elementos):
        errores.agregar(campo, f"Cada elemento admite máximo {max_largo} caracteres.")
        return None
    return elementos


def _vacio(valor):
    return valor is None or (isinstance(valor, str) and not valor.strip())


def entero_obligatorio(errores, datos, campo, minimo=None, maximo=None):
    if _vacio(datos.get(campo)):
        errores.agregar(campo, "Es obligatorio.")
        return None
    return entero_opcional(errores, datos, campo, minimo, maximo)


def decimal_obligatorio(errores, datos, campo, minimo=None, decimales=None, maximo=None):
    if _vacio(datos.get(campo)):
        errores.agregar(campo, "Es obligatorio.")
        return None
    return decimal_opcional(errores, datos, campo, minimo, decimales, maximo)


def _codigo(errores, datos, campo, maximo, patron, mensaje):
    """Texto obligatorio que se recorta, se pasa a mayúsculas y debe cumplir `patron`."""
    valor = texto_obligatorio(errores, datos, campo, maximo)
    if valor is None:
        return None
    valor = valor.upper()
    if not patron.fullmatch(valor):
        errores.agregar(campo, mensaje)
        return None
    return valor


def sku(errores, datos, campo, maximo):
    """SKU obligatorio: letras, dígitos, guion, guion bajo y punto, sin espacios."""
    return _codigo(
        errores, datos, campo, maximo, PATRON_SKU,
        "Solo admite letras, dígitos, guion, guion bajo y punto, sin espacios.")


def codigo_bodega(errores, datos, campo, maximo):
    """Código de bodega obligatorio: letras, dígitos, guion y guion bajo, sin espacios."""
    return _codigo(
        errores, datos, campo, maximo, PATRON_CODIGO_BODEGA,
        "Solo admite letras, dígitos, guion y guion bajo, sin espacios.")
