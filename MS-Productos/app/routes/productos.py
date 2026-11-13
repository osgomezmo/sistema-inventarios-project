from flask import Blueprint, jsonify, request

from app.db import transaccion
from app.errors import ApiError
from app.paginacion import leer_paginacion, respuesta_paginada
from app.repositorios import productos as repo
from app.validacion import (
    Errores,
    decimal_opcional,
    entero_opcional,
    lista_separada_por_comas,
    opcion,
)

productos_bp = Blueprint("productos", __name__)

ESTADOS = ("ACTIVO", "INACTIVO")
MAX_SKUS = 100
LARGO_SKU = 50


def no_existe():
    return ApiError("NO_EXISTE", "El producto no existe.", 404)


def leer_filtros(errores):
    """Lee y valida los filtros del listado; los errores se acumulan en `errores`."""
    args = request.args
    precio_min = decimal_opcional(errores, args, "precio_min", minimo=0, decimales=2)
    precio_max = decimal_opcional(errores, args, "precio_max", minimo=0, decimales=2)
    if precio_min is not None and precio_max is not None and precio_min > precio_max:
        errores.agregar("precio_min", "No puede ser mayor que precio_max.")

    return {
        "q": args.get("q", "").strip() or None,
        "id_categoria": entero_opcional(errores, args, "id_categoria", minimo=1),
        "estado": opcion(errores, args, "estado", ESTADOS),
        "precio_min": precio_min,
        "precio_max": precio_max,
        "skus": lista_separada_por_comas(errores, args, "skus", MAX_SKUS, LARGO_SKU),
    }


@productos_bp.get("/productos")
def listar_productos():
    errores = Errores()
    page, per_page, offset = leer_paginacion(errores)
    filtros = leer_filtros(errores)
    errores.lanzar_si_hay()

    # ?skus presente pero sin elementos: no hay nada que buscar.
    if filtros["skus"] == []:
        return jsonify(respuesta_paginada([], page, per_page, 0))

    with transaccion() as cursor:
        filas, total = repo.listar(cursor, per_page, offset, **filtros)
    return jsonify(respuesta_paginada(filas, page, per_page, total))


@productos_bp.get("/productos/<int:id_producto>")
def obtener_producto(id_producto):
    with transaccion() as cursor:
        producto = repo.obtener(cursor, id_producto)
    if producto is None:
        raise no_existe()
    return jsonify(producto)


@productos_bp.get("/productos/sku/<sku>")
def obtener_producto_por_sku(sku):
    # Consulta síncrona de ms-inventario: también devuelve productos inactivos.
    with transaccion() as cursor:
        producto = repo.obtener_por_sku(cursor, sku)
    if producto is None:
        raise no_existe()
    return jsonify(producto)
