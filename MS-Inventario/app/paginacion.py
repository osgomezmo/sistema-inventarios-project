"""Paginación de listados: ?page=1&per_page=20, con per_page máximo de 100."""

from flask import request

from app.validacion import Errores, entero_opcional

PAGINA_POR_DEFECTO = 1
POR_PAGINA_POR_DEFECTO = 20
POR_PAGINA_MAXIMO = 100


def leer_paginacion(errores=None):
    """Lee page y per_page de la query string y devuelve (page, per_page, offset).

    Si se pasa `errores`, los problemas se acumulan ahí para responderlos junto
    con los de otros filtros; si no, se lanza el 422 de inmediato.
    """
    propios = errores is None
    errores = Errores() if propios else errores

    page = entero_opcional(errores, request.args, "page", minimo=1)
    per_page = entero_opcional(
        errores, request.args, "per_page", minimo=1, maximo=POR_PAGINA_MAXIMO
    )
    if propios:
        errores.lanzar_si_hay()

    page = page or PAGINA_POR_DEFECTO
    per_page = per_page or POR_PAGINA_POR_DEFECTO
    return page, per_page, (page - 1) * per_page


def respuesta_paginada(datos, page, per_page, total):
    return {"data": datos, "meta": {"page": page, "per_page": per_page, "total": total}}
