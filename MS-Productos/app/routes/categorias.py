from flask import Blueprint, jsonify, request

from app.db import transaccion
from app.errors import ApiError
from app.paginacion import leer_paginacion, respuesta_paginada
from app.repositorios import categorias as repo
from app.validacion import Errores, entero_opcional, opcion

categorias_bp = Blueprint("categorias", __name__)

ESTADOS = ("ACTIVO", "INACTIVO")


@categorias_bp.get("/categorias")
def listar_categorias():
    errores = Errores()
    page, per_page, offset = leer_paginacion(errores)
    estado = opcion(errores, request.args, "estado", ESTADOS)
    id_padre = entero_opcional(errores, request.args, "id_padre", minimo=1)
    errores.lanzar_si_hay()

    with transaccion() as cursor:
        # Con id_padre: lista plana de los hijos de esa categoría.
        if id_padre is not None:
            filas, total = repo.listar_hijas(cursor, id_padre, estado, per_page, offset)
            return jsonify(respuesta_paginada(filas, page, per_page, total))

        # Sin id_padre: raíces con sus subcategorías, traídas en una sola consulta.
        raices, total = repo.listar_raices(cursor, estado, per_page, offset)
        hijas = repo.subcategorias_por_padre(
            cursor, [r["id_categoria"] for r in raices], estado
        )

    for raiz in raices:
        raiz["subcategorias"] = hijas[raiz["id_categoria"]]
    return jsonify(respuesta_paginada(raices, page, per_page, total))


@categorias_bp.get("/categorias/<int:id_categoria>")
def obtener_categoria(id_categoria):
    with transaccion() as cursor:
        categoria = repo.obtener(cursor, id_categoria)
        if categoria is None:
            raise ApiError("NO_EXISTE", "La categoría no existe.", 404)
        # Una raíz lleva todas sus subcategorías; una subcategoría no lleva el campo.
        if categoria["id_categoria_padre"] is None:
            categoria["subcategorias"] = repo.subcategorias_por_padre(
                cursor, [id_categoria]
            )[id_categoria]

    return jsonify(categoria)
