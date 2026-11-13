from flask import Blueprint, jsonify, request

from app.db import transaccion
from app.errors import ApiError
from app.paginacion import leer_paginacion, respuesta_paginada
from app.repositorios import categorias as repo
from app.validacion import (
    Errores,
    entero_opcional,
    leer_json,
    opcion,
    texto_obligatorio,
    texto_opcional,
)

categorias_bp = Blueprint("categorias", __name__)

ESTADOS = ("ACTIVO", "INACTIVO")
CAMPO_PADRE = "id_categoria_padre"


def no_existe():
    return ApiError("NO_EXISTE", "La categoría no existe.", 404)


def con_subcategorias(cursor, categoria):
    """Una raíz lleva todas sus subcategorías; una subcategoría no lleva el campo."""
    if categoria["id_categoria_padre"] is None:
        id_categoria = categoria["id_categoria"]
        categoria["subcategorias"] = repo.subcategorias_por_padre(cursor, [id_categoria])[
            id_categoria
        ]
    return categoria


def leer_cuerpo():
    """Valida el cuerpo de POST y PUT. Los campos desconocidos se ignoran."""
    datos = leer_json()
    errores = Errores()
    nombre = texto_obligatorio(errores, datos, "nombre", 100)
    descripcion = texto_opcional(errores, datos, "descripcion", 255)
    id_padre = entero_opcional(errores, datos, CAMPO_PADRE, minimo=1)
    errores.lanzar_si_hay()
    return nombre, descripcion, id_padre


def validar_padre(cursor, id_padre):
    """El padre debe existir, estar ACTIVO y ser raíz (máximo dos niveles)."""
    if id_padre is None:
        return
    padre = repo.obtener_bloqueando(cursor, id_padre)
    if padre is None:
        mensaje = "La categoría padre no existe."
    elif padre["estado"] != "ACTIVO":
        mensaje = "La categoría padre está inactiva."
    elif padre["id_categoria_padre"] is not None:
        mensaje = "La categoría padre debe ser una categoría raíz (máximo dos niveles)."
    else:
        return
    raise ApiError("VALIDACION", "Revisa los campos enviados.", 422, {CAMPO_PADRE: [mensaje]})


def validar_nombre_libre(cursor, nombre, id_padre, excluir_id=None):
    if repo.nombre_repetido(cursor, nombre, id_padre, excluir_id):
        raise ApiError(
            "NOMBRE_REPETIDO",
            "Ya existe una categoría con ese nombre en el mismo nivel.",
            409,
            {"nombre": ["Ya existe una categoría con ese nombre en el mismo nivel."]},
        )


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
            raise no_existe()
        return jsonify(con_subcategorias(cursor, categoria))


@categorias_bp.post("/categorias")
def crear_categoria():
    nombre, descripcion, id_padre = leer_cuerpo()

    with transaccion() as cursor:
        validar_padre(cursor, id_padre)
        validar_nombre_libre(cursor, nombre, id_padre)
        id_categoria = repo.insertar(cursor, nombre, descripcion, id_padre)
        categoria = con_subcategorias(cursor, repo.obtener(cursor, id_categoria))

    return jsonify(categoria), 201


@categorias_bp.put("/categorias/<int:id_categoria>")
def editar_categoria(id_categoria):
    # D29: reemplazo completo; lo que no venga queda en NULL y el estado no cambia.
    nombre, descripcion, id_padre = leer_cuerpo()

    with transaccion() as cursor:
        if repo.obtener_bloqueando(cursor, id_categoria) is None:
            raise no_existe()

        if id_padre is not None:
            if id_padre == id_categoria:
                raise ApiError(
                    "VALIDACION", "Revisa los campos enviados.", 422,
                    {CAMPO_PADRE: ["Una categoría no puede ser su propio padre."]},
                )
            if repo.contar_subcategorias(cursor, id_categoria) > 0:
                raise ApiError(
                    "VALIDACION", "Revisa los campos enviados.", 422,
                    {CAMPO_PADRE: [
                        "La categoría tiene subcategorías y no puede pasar a ser subcategoría."
                    ]},
                )
            validar_padre(cursor, id_padre)

        validar_nombre_libre(cursor, nombre, id_padre, excluir_id=id_categoria)
        repo.actualizar(cursor, id_categoria, nombre, descripcion, id_padre)
        categoria = con_subcategorias(cursor, repo.obtener(cursor, id_categoria))

    return jsonify(categoria)


@categorias_bp.post("/categorias/<int:id_categoria>/inactivar")
def inactivar_categoria(id_categoria):
    # El cuerpo, si viene, se ignora.
    with transaccion() as cursor:
        categoria = repo.obtener_bloqueando(cursor, id_categoria)
        if categoria is None:
            raise no_existe()
        # Idempotente: si ya está inactiva, se responde sin cambios.
        if categoria["estado"] == "INACTIVO":
            return jsonify(con_subcategorias(cursor, categoria))

        # Una raíz arrastra a todas sus subcategorías; una subcategoría, solo a sí misma.
        ids = [id_categoria]
        if categoria["id_categoria_padre"] is None:
            ids += [s["id_categoria"] for s in repo.bloquear_subcategorias(cursor, id_categoria)]

        if repo.contar_productos_activos(cursor, ids) > 0:
            raise ApiError(
                "CATEGORIA_CON_PRODUCTOS",
                "No se puede inactivar: la categoría o alguna de sus subcategorías"
                " tiene productos activos.",
                409,
            )

        repo.actualizar_estado(cursor, ids, "INACTIVO")
        return jsonify(con_subcategorias(cursor, repo.obtener(cursor, id_categoria)))


@categorias_bp.post("/categorias/<int:id_categoria>/activar")
def activar_categoria(id_categoria):
    # El cuerpo, si viene, se ignora.
    with transaccion() as cursor:
        categoria = repo.obtener(cursor, id_categoria)
        if categoria is None:
            raise no_existe()

        # Se bloquea primero la raíz y luego la subcategoría, el mismo orden que
        # usa inactivar, para no cruzar bloqueos entre las dos operaciones.
        id_padre = categoria["id_categoria_padre"]
        padre = repo.obtener_bloqueando(cursor, id_padre) if id_padre is not None else None
        categoria = repo.obtener_bloqueando(cursor, id_categoria)
        if categoria["id_categoria_padre"] != id_padre:
            raise ApiError(
                "CONFLICTO",
                "La categoría cambió de nivel mientras se activaba; intenta de nuevo.",
                409,
            )

        # Idempotente: si ya está activa, se responde sin cambios.
        if categoria["estado"] == "ACTIVO":
            return jsonify(con_subcategorias(cursor, categoria))

        # Una subcategoría necesita su raíz activa. Activar una raíz no reactiva sus hijas.
        if padre is not None and padre["estado"] != "ACTIVO":
            raise ApiError(
                "CONFLICTO",
                "No se puede activar la subcategoría porque su categoría raíz está"
                " inactiva. Activa primero la raíz.",
                409,
            )

        repo.actualizar_estado(cursor, [id_categoria], "ACTIVO")
        categoria["estado"] = "ACTIVO"
        return jsonify(con_subcategorias(cursor, categoria))
