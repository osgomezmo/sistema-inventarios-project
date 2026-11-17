from decimal import Decimal

from flask import Blueprint, jsonify, request

from app.db import transaccion
from app.errors import ApiError
from app.repositorios import kardex as repo
from app.routes.movimientos import LARGO_SKU, MAX_ID, leer_rango_de_fechas
from app.validacion import MENSAJE_VALIDACION, Errores, entero_obligatorio, texto_obligatorio

kardex_bp = Blueprint("kardex", __name__)

MAX_MOVIMIENTOS = 5000
CERO = {"cantidad": Decimal("0"), "valor": Decimal("0")}


def _saldo(fila):
    return {"cantidad": fila["saldo_resultante"], "valor": fila["valor_resultante"]}


@kardex_bp.get("/kardex")
def consultar_kardex():
    args = request.args
    errores = Errores()
    sku = texto_obligatorio(errores, args, "sku", LARGO_SKU)
    id_bodega = entero_obligatorio(errores, args, "id_bodega", minimo=1, maximo=MAX_ID)
    for campo in ("desde", "hasta"):
        if not (args.get(campo) or "").strip():
            errores.agregar(campo, "Es obligatorio.")
    desde, hasta = leer_rango_de_fechas(errores, args)
    errores.lanzar_si_hay()

    (inicio, _), (fin, fin_inclusivo) = desde, hasta
    with transaccion() as cursor:
        previo = repo.saldo_anterior(cursor, sku, id_bodega, inicio)
        # Se pide una fila de más para saber si el rango supera el máximo.
        movimientos = repo.movimientos_en_rango(
            cursor, sku, id_bodega, inicio, fin, fin_inclusivo, MAX_MOVIMIENTOS + 1)

    if len(movimientos) > MAX_MOVIMIENTOS:
        raise ApiError(
            "VALIDACION", MENSAJE_VALIDACION, 422,
            {"desde": [f"El rango tiene más de {MAX_MOVIMIENTOS} movimientos; acota las fechas."]},
        )

    saldo_inicial = _saldo(previo) if previo else dict(CERO)
    saldo_final = _saldo(movimientos[-1]) if movimientos else dict(saldo_inicial)
    return jsonify({
        "sku": sku,
        "id_bodega": id_bodega,
        "desde": args["desde"].strip(),
        "hasta": args["hasta"].strip(),
        "saldo_inicial": saldo_inicial,
        "movimientos": movimientos,
        "saldo_final": saldo_final,
    })
