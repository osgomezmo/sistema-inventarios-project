import re

from flask import Blueprint, current_app, jsonify, request

from app import eventos
from app.clientes.productos import consultar_producto
from app.db import ejecutar_con_reintento, transaccion
from app.errors import ApiError
from app.paginacion import leer_paginacion, respuesta_paginada
from app.repositorios import movimientos as repo
from app.servicios.movimientos import MAX_CANTIDAD, MAX_COSTO, aplicar_movimiento
from app.validacion import (
    Errores,
    decimal_obligatorio,
    decimal_opcional,
    entero_obligatorio,
    entero_opcional,
    fecha_opcional,
    leer_json,
    opcion,
    texto_opcional,
)
from app.validacion import sku as validar_sku

movimientos_bp = Blueprint("movimientos", __name__)

TIPOS = (
    "ENTRADA_COMPRA", "AJUSTE_POSITIVO", "TRASLADO_ENTRADA", "DEVOLUCION_CLIENTE",
    "SALIDA", "AJUSTE_NEGATIVO", "TRASLADO_SALIDA", "DEVOLUCION_PROVEEDOR",
)
LARGO_SKU = 50
TIPOS_MANUALES = ("SALIDA", "AJUSTE_POSITIVO", "AJUSTE_NEGATIVO")
MAX_ID = 2147483647  # INT de MySQL
PATRON_ID_USUARIO = re.compile(r"\d+")


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


def leer_id_usuario():
    """X-User-Id obligatorio en las escrituras (D4): entero positivo, si no 400."""
    valor = (request.headers.get("X-User-Id") or "").strip()
    if PATRON_ID_USUARIO.fullmatch(valor) and 0 < int(valor) <= MAX_ID:
        return int(valor)
    raise ApiError(
        "PETICION_INVALIDA",
        "La cabecera X-User-Id es obligatoria y debe ser un entero positivo.",
        400,
    )


def leer_cuerpo_movimiento():
    """Valida el cuerpo de POST /movimientos; todos los errores en un solo 422."""
    datos = leer_json()
    errores = Errores()
    campos = {
        "sku": validar_sku(errores, datos, "sku", LARGO_SKU),
        "id_bodega": entero_obligatorio(errores, datos, "id_bodega", minimo=1, maximo=MAX_ID),
        "tipo": opcion(errores, datos, "tipo", TIPOS_MANUALES, obligatorio=True),
        "cantidad": decimal_obligatorio(
            errores, datos, "cantidad", minimo=0, decimales=3, maximo=MAX_CANTIDAD),
        "costo_unitario": decimal_opcional(
            errores, datos, "costo_unitario", minimo=0, decimales=4, maximo=MAX_COSTO),
        "motivo": texto_opcional(errores, datos, "motivo", 255),
        "documento_referencia": texto_opcional(errores, datos, "documento_referencia", 100),
    }
    if campos["cantidad"] is not None and campos["cantidad"] == 0:
        errores.agregar("cantidad", "Debe ser mayor que 0.")
    errores.lanzar_si_hay()
    return campos


@movimientos_bp.post("/movimientos")
def registrar_movimiento():
    id_usuario = leer_id_usuario()
    id_correlacion = (request.headers.get("X-Correlation-Id") or "").strip() or None
    campos = leer_cuerpo_movimiento()

    # Fuera de la transacción: nunca se espera a ms-productos con filas bloqueadas (D22).
    producto = consultar_producto(campos["sku"], id_correlacion)

    def operar():
        with transaccion() as cursor:
            resultado = aplicar_movimiento(
                cursor,
                sku=producto["sku"],  # el canónico de ms-productos (D39)
                id_bodega=campos["id_bodega"],
                tipo=campos["tipo"],
                cantidad=campos["cantidad"],
                id_usuario=id_usuario,
                unidad_medida=producto["unidad_medida"],
                stock_minimo=producto["stock_minimo"],
                costo_unitario=campos["costo_unitario"],
                motivo=campos["motivo"],
                documento_referencia=campos["documento_referencia"],
            )
            # Mismo formato que GET /movimientos/{id} (D43, sin id_traslado).
            resultado["respuesta"] = repo.obtener(cursor, resultado["movimiento"]["id_movimiento"])
            return resultado

    resultado = ejecutar_con_reintento(operar)

    # Ya confirmado: un fallo al avisar no cambia la respuesta (D8).
    try:
        eventos.publicar_movimiento(resultado, id_correlacion)
    except Exception:
        current_app.logger.exception("No se pudo procesar el aviso del movimiento.")

    return jsonify(resultado["respuesta"]), 201
