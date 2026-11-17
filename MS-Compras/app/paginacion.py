"""Utilidades estandar de paginacion (?page=1&per_page=20, max 100)."""

import math

from flask import request

from app.errors import ErrorAPI

PAGINA_DEFECTO = 1
POR_PAGINA_DEFECTO = 20
POR_PAGINA_MAXIMO = 100


def obtener_parametros_paginacion() -> tuple[int, int, int]:
    """Extrae y valida page, per_page y offset desde los query params."""
    page_raw = request.args.get("page", str(PAGINA_DEFECTO)).strip()
    per_page_raw = request.args.get("per_page", str(POR_PAGINA_DEFECTO)).strip()

    try:
        page = int(page_raw)
        per_page = int(per_page_raw)
    except ValueError as exc:
        raise ErrorAPI(
            422,
            "VALIDACION",
            "Los parametros page y per_page deben ser enteros.",
        ) from exc

    if page < 1:
        raise ErrorAPI(422, "VALIDACION", "El parametro page debe ser mayor o igual a 1.")

    if per_page < 1 or per_page > POR_PAGINA_MAXIMO:
        raise ErrorAPI(
            422,
            "VALIDACION",
            f"El parametro per_page debe estar entre 1 y {POR_PAGINA_MAXIMO}.",
        )

    offset = (page - 1) * per_page
    return page, per_page, offset


def construir_meta(total: int, page: int, per_page: int) -> dict[str, int]:
    """Construye el objeto meta estandar para listados paginados."""
    total_pages = math.ceil(total / per_page) if total > 0 else 0
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
    }
