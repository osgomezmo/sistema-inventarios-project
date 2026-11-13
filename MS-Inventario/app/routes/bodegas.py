from flask import Blueprint, jsonify, request

from app.db import transaccion
from app.errors import ApiError
from app.paginacion import leer_paginacion, respuesta_paginada
from app.repositorios import bodegas as repo
from app.validacion import Errores, opcion

bodegas_bp = Blueprint("bodegas", __name__)

ESTADOS = ("ACTIVO", "INACTIVO")


def no_existe():
    return ApiError("NO_EXISTE", "La bodega no existe.", 404)


@bodegas_bp.get("/bodegas")
def listar_bodegas():
    errores = Errores()
    page, per_page, offset = leer_paginacion(errores)
    estado = opcion(errores, request.args, "estado", ESTADOS)
    errores.lanzar_si_hay()

    with transaccion() as cursor:
        filas, total = repo.listar(cursor, estado, per_page, offset)
    return jsonify(respuesta_paginada(filas, page, per_page, total))


@bodegas_bp.get("/bodegas/<int:id_bodega>")
def obtener_bodega(id_bodega):
    with transaccion() as cursor:
        bodega = repo.obtener(cursor, id_bodega)
    if bodega is None:
        raise no_existe()
    return jsonify(bodega)
