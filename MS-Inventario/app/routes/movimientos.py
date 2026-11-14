from flask import Blueprint, jsonify, request

from app.db import transaccion
from app.errors import ApiError
from app.paginacion import leer_paginacion, respuesta_paginada
from app.repositorios import movimientos as repo
from app.validacion import Errores, entero_opcional, fecha_opcional, opcion, texto_opcional

movimientos_bp = Blueprint("movimientos", __name__)

TIPOS = (
    "ENTRADA_COMPRA", "AJUSTE_POSITIVO", "TRASLADO_ENTRADA", "DEVOLUCION_CLIENTE",
    "SALIDA", "AJUSTE_NEGATIVO", "TRASLADO_SALIDA", "DEVOLUCION_PROVEEDOR",
)
LARGO_SKU = 50


def leer_rango_de_fechas(errores, args):
    """Lee desde y hasta (D15, D43) y comprueba que desde no quede después de hasta."""
    desde = fecha_opcional(errores, "desde", args.get("desde"))
    hasta = fecha_opcional(errores, "hasta", args.get("hasta"), limite_superior=True)
    if desde and hasta:
        (inicio, _), (fin, inclusivo) = desde, hasta
        if inicio > fin or (inicio == fin and not inclusivo):
            errores.agregar("desde", "No puede ser posterior a hasta.")
    return desde, hasta


@movimientos_bp.get("/movimientos")
def listar_movimientos():
    errores = Errores()
    page, per_page, offset = leer_paginacion(errores)
    desde, hasta = leer_rango_de_fechas(errores, request.args)
    filtros = {
        "sku": texto_opcional(errores, request.args, "sku", LARGO_SKU),
        "id_bodega": entero_opcional(errores, request.args, "id_bodega", minimo=1),
        "tipo": opcion(errores, request.args, "tipo", TIPOS),
        "desde": desde,
        "hasta": hasta,
    }
    errores.lanzar_si_hay()

    with transaccion() as cursor:
        filas, total = repo.listar(cursor, per_page, offset, **filtros)
    return jsonify(respuesta_paginada(filas, page, per_page, total))


@movimientos_bp.get("/movimientos/<int:id_movimiento>")
def obtener_movimiento(id_movimiento):
    with transaccion() as cursor:
        movimiento = repo.obtener(cursor, id_movimiento)
    if movimiento is None:
        raise ApiError("NO_EXISTE", "El movimiento no existe.", 404)
    return jsonify(movimiento)
