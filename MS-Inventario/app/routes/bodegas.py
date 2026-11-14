import mysql.connector
from flask import Blueprint, jsonify, request

from app.db import transaccion
from app.errors import ApiError
from app.paginacion import leer_paginacion, respuesta_paginada
from app.repositorios import bodegas as repo
from app.validacion import Errores, codigo_bodega, leer_json, opcion, texto_obligatorio

bodegas_bp = Blueprint("bodegas", __name__)

ESTADOS = ("ACTIVO", "INACTIVO")
ERROR_DUPLICADO = 1062


def no_existe():
    return ApiError("NO_EXISTE", "La bodega no existe.", 404)


def leer_cuerpo_bodega(con_codigo):
    """Valida el cuerpo de POST (con código) y PUT (sin código).

    El estado y los campos desconocidos se ignoran. Todos los errores salen
    juntos en un 422.
    """
    datos = leer_json()
    errores = Errores()
    campos = {
        "nombre": texto_obligatorio(errores, datos, "nombre", 100),
        "direccion": texto_obligatorio(errores, datos, "direccion", 255),
    }
    if con_codigo:
        campos["codigo"] = codigo_bodega(errores, datos, "codigo", 30)
    errores.lanzar_si_hay()
    return campos


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


@bodegas_bp.post("/bodegas")
def crear_bodega():
    campos = leer_cuerpo_bodega(con_codigo=True)

    with transaccion() as cursor:
        # Sin SELECT previo del código: el índice único decide y el duplicado es 409.
        try:
            id_bodega = repo.insertar(cursor, **campos)
        except mysql.connector.IntegrityError as error:
            if error.errno != ERROR_DUPLICADO:
                raise
            raise ApiError(
                "CODIGO_DUPLICADO",
                "Ya existe una bodega con ese código.",
                409,
                {"codigo": ["Ya existe una bodega con ese código."]},
            ) from None
        bodega = repo.obtener(cursor, id_bodega)

    return jsonify(bodega), 201


@bodegas_bp.put("/bodegas/<int:id_bodega>")
def editar_bodega(id_bodega):
    # D36: reemplaza nombre y dirección; el código y el estado del cuerpo se ignoran.
    campos = leer_cuerpo_bodega(con_codigo=False)

    with transaccion() as cursor:
        if repo.obtener_bloqueando(cursor, id_bodega) is None:
            raise no_existe()
        repo.actualizar(cursor, id_bodega, **campos)
        bodega = repo.obtener(cursor, id_bodega)

    return jsonify(bodega)
