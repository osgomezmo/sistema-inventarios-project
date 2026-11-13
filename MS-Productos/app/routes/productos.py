from decimal import Decimal

import mysql.connector
from flask import Blueprint, jsonify, request

from app.db import transaccion
from app.errors import ApiError
from app.paginacion import leer_paginacion, respuesta_paginada
from app.repositorios import categorias as repo_categorias
from app.repositorios import productos as repo
from app.validacion import (
    MENSAJE_VALIDACION,
    Errores,
    decimal_obligatorio,
    decimal_opcional,
    entero_obligatorio,
    entero_opcional,
    leer_json,
    lista_separada_por_comas,
    opcion,
    texto_obligatorio,
    texto_opcional,
)
from app.validacion import sku as validar_sku

productos_bp = Blueprint("productos", __name__)

ESTADOS = ("ACTIVO", "INACTIVO")
UNIDADES = ("UNIDAD", "KILO", "LITRO")
MAX_SKUS = 100
LARGO_SKU = 50
MAX_PRECIO = Decimal("999999999999.99")  # DECIMAL(14,2)
MAX_STOCK = Decimal("99999999999.999")  # DECIMAL(14,3)
ERROR_DUPLICADO = 1062


def no_existe():
    return ApiError("NO_EXISTE", "El producto no existe.", 404)


def leer_cuerpo_producto(con_sku):
    """Valida el cuerpo de POST (con_sku=True) y PUT (sin SKU).

    Devuelve un diccionario con los campos ya normalizados. El estado y los
    campos desconocidos se ignoran. Todos los errores salen juntos en un 422.
    """
    datos = leer_json()
    errores = Errores()
    campos = {
        "nombre": texto_obligatorio(errores, datos, "nombre", 150),
        "descripcion": texto_opcional(errores, datos, "descripcion", 1000),
        "marca": texto_obligatorio(errores, datos, "marca", 100),
        "id_categoria": entero_obligatorio(errores, datos, "id_categoria", minimo=1),
        "unidad_medida": opcion(errores, datos, "unidad_medida", UNIDADES, obligatorio=True),
        "precio_venta": decimal_obligatorio(
            errores, datos, "precio_venta", minimo=0, decimales=2, maximo=MAX_PRECIO),
        "stock_minimo": decimal_obligatorio(
            errores, datos, "stock_minimo", minimo=0, decimales=3, maximo=MAX_STOCK),
    }
    if con_sku:
        campos["sku"] = validar_sku(errores, datos, "sku", LARGO_SKU)

    # D9: con UNIDAD, el stock mínimo es un número entero.
    stock = campos["stock_minimo"]
    es_unidad = campos["unidad_medida"] == "UNIDAD"
    if es_unidad and stock is not None and stock != stock.to_integral_value():
        errores.agregar("stock_minimo", "Con unidad_medida UNIDAD debe ser un número entero.")

    errores.lanzar_si_hay()
    return campos


def validar_categoria(cursor, id_categoria):
    """La categoría debe existir y estar ACTIVA. Se lee con FOR SHARE para que
    no la inactiven mientras se guarda el producto."""
    categoria = repo_categorias.obtener_compartido(cursor, id_categoria)
    if categoria is None:
        mensaje = "La categoría no existe."
    elif categoria["estado"] != "ACTIVO":
        mensaje = "La categoría está inactiva."
    else:
        return
    raise ApiError("VALIDACION", MENSAJE_VALIDACION, 422, {"id_categoria": [mensaje]})


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


@productos_bp.post("/productos")
def crear_producto():
    campos = leer_cuerpo_producto(con_sku=True)

    with transaccion() as cursor:
        validar_categoria(cursor, campos["id_categoria"])
        # Sin SELECT previo del SKU: el índice único decide y el duplicado se traduce a 409.
        try:
            id_producto = repo.insertar(cursor, **campos)
        except mysql.connector.IntegrityError as error:
            if error.errno != ERROR_DUPLICADO:
                raise
            raise ApiError(
                "SKU_DUPLICADO",
                "Ya existe un producto con ese SKU.",
                409,
                {"sku": ["Ya existe un producto con ese SKU."]},
            ) from None
        producto = repo.obtener(cursor, id_producto)

    return jsonify(producto), 201
