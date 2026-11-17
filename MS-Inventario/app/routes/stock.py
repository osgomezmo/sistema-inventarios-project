from decimal import Decimal

from flask import Blueprint, jsonify, request

from app.db import transaccion
from app.errors import ApiError
from app.paginacion import leer_paginacion, respuesta_paginada
from app.repositorios import stock as repo
from app.validacion import Errores, booleano_opcional, entero_opcional, texto_opcional

stock_bp = Blueprint("stock", __name__)

LARGO_SKU = 50


def sin_saldos():
    return ApiError("NO_EXISTE", "No hay saldos para ese SKU.", 404)


@stock_bp.get("/stock")
def listar_stock():
    errores = Errores()
    page, per_page, offset = leer_paginacion(errores)
    filtros = {
        "sku": texto_opcional(errores, request.args, "sku", LARGO_SKU),
        "id_bodega": entero_opcional(errores, request.args, "id_bodega", minimo=1),
        "bajo_minimo": booleano_opcional(errores, request.args, "bajo_minimo"),
    }
    errores.lanzar_si_hay()

    with transaccion() as cursor:
        filas, total = repo.listar(cursor, per_page, offset, **filtros)
    return jsonify(respuesta_paginada(filas, page, per_page, total))


@stock_bp.get("/stock/<sku>")
def stock_de_sku(sku):
    # Un SKU más largo que la columna no puede existir.
    if len(sku) > LARGO_SKU:
        raise sin_saldos()

    with transaccion() as cursor:
        filas = repo.saldos_de_sku(cursor, sku)
    if not filas:
        raise sin_saldos()

    por_bodega = [
        {k: f[k] for k in ("id_bodega", "cantidad", "costo_promedio", "valor")} for f in filas
    ]
    total = {
        "cantidad": sum((f["cantidad"] for f in filas), Decimal("0")),
        "valor": sum((f["valor"] for f in filas), Decimal("0")),
    }
    # Se devuelve el SKU tal como está guardado, aunque se haya pedido en minúsculas.
    return jsonify({"sku": filas[0]["sku"], "por_bodega": por_bodega, "total": total})
