from flask import Blueprint, current_app, jsonify, request

from app import eventos
from app.clientes.productos import consultar_producto
from app.db import ejecutar_con_reintento, transaccion
from app.errors import ApiError
from app.paginacion import leer_paginacion, respuesta_paginada
from app.repositorios import saldos as repo_saldos
from app.repositorios import traslados as repo
from app.routes.movimientos import LARGO_SKU, MAX_ID, leer_id_usuario, leer_rango_de_fechas
from app.servicios.movimientos import MAX_CANTIDAD, aplicar_movimiento
from app.validacion import (
    MENSAJE_VALIDACION,
    Errores,
    decimal_obligatorio,
    entero_obligatorio,
    leer_json,
    texto_opcional,
)
from app.validacion import sku as validar_sku

traslados_bp = Blueprint("traslados", __name__)


def no_existe():
    return ApiError("NO_EXISTE", "El traslado no existe.", 404)


def leer_cuerpo_traslado():
    """Valida el cuerpo de POST /traslados; todos los errores en un solo 422."""
    datos = leer_json()
    errores = Errores()
    campos = {
        "sku": validar_sku(errores, datos, "sku", LARGO_SKU),
        "id_bodega_origen": entero_obligatorio(
            errores, datos, "id_bodega_origen", minimo=1, maximo=MAX_ID),
        "id_bodega_destino": entero_obligatorio(
            errores, datos, "id_bodega_destino", minimo=1, maximo=MAX_ID),
        "cantidad": decimal_obligatorio(
            errores, datos, "cantidad", minimo=0, decimales=3, maximo=MAX_CANTIDAD),
        "motivo": texto_opcional(errores, datos, "motivo", 255),
    }
    if campos["cantidad"] is not None and campos["cantidad"] == 0:
        errores.agregar("cantidad", "Debe ser mayor que 0.")
    origen, destino = campos["id_bodega_origen"], campos["id_bodega_destino"]
    if origen is not None and origen == destino:
        errores.agregar("id_bodega_destino", "Debe ser distinta de la bodega de origen.")
    errores.lanzar_si_hay()
    return campos


def _validar_bodegas(cursor, origen, destino):
    """Lee las dos bodegas con FOR SHARE en orden ascendente de id."""
    campo_de = {origen: "id_bodega_origen", destino: "id_bodega_destino"}
    for id_bodega in sorted(campo_de):
        bodega = repo_saldos.leer_bodega_compartida(cursor, id_bodega)
        if bodega is None:
            raise ApiError("NO_EXISTE", "La bodega no existe.", 404,
                           {campo_de[id_bodega]: ["La bodega no existe."]})
        if bodega["estado"] != "ACTIVO":
            raise ApiError("VALIDACION", MENSAJE_VALIDACION, 422,
                           {campo_de[id_bodega]: ["La bodega está inactiva."]})


def _bloquear_saldos(cursor, sku, origen, destino, stock_minimo):
    """Bloquea los dos saldos en orden ascendente de id_bodega, para que dos
    traslados cruzados no se esperen en orden opuesto (D46)."""
    for id_bodega in sorted((origen, destino)):
        if id_bodega == destino:
            repo_saldos.asegurar_saldo(cursor, sku, destino, stock_minimo)
            repo_saldos.bloquear_saldo(cursor, sku, destino)
        elif repo_saldos.bloquear_saldo(cursor, sku, origen) is None:
            raise ApiError(
                "STOCK_INSUFICIENTE", "No hay saldo suficiente para esta salida.", 409,
                {"cantidad": ["Saldo disponible: 0."]},
            )


@traslados_bp.post("/traslados")
def registrar_traslado():
    id_usuario = leer_id_usuario()
    id_correlacion = (request.headers.get("X-Correlation-Id") or "").strip() or None
    campos = leer_cuerpo_traslado()
    # Fuera de la transacción (D22).
    producto = consultar_producto(campos["sku"], id_correlacion)
    sku, origen, destino = producto["sku"], campos["id_bodega_origen"], campos["id_bodega_destino"]

    def operar():
        with transaccion() as cursor:
            _validar_bodegas(cursor, origen, destino)
            _bloquear_saldos(cursor, sku, origen, destino, producto["stock_minimo"])
            id_traslado = repo.insertar(
                cursor, sku, origen, destino, campos["cantidad"], campos["motivo"], id_usuario)
            comunes = {
                "sku": sku, "cantidad": campos["cantidad"], "id_usuario": id_usuario,
                "unidad_medida": producto["unidad_medida"],
                "stock_minimo": producto["stock_minimo"], "motivo": campos["motivo"],
                "documento_referencia": f"TR-{id_traslado}", "id_traslado": id_traslado,
            }
            salida = aplicar_movimiento(
                cursor, id_bodega=origen, tipo="TRASLADO_SALIDA", **comunes)
            entrada = aplicar_movimiento(
                cursor, id_bodega=destino, tipo="TRASLADO_ENTRADA",
                costo_unitario=salida["movimiento"]["costo_promedio"], **comunes)
            return repo.obtener(cursor, id_traslado), (salida, entrada)

    traslado, resultados = ejecutar_con_reintento(operar)

    # Ya confirmado: un fallo al avisar no cambia la respuesta (D8).
    for resultado in resultados:
        try:
            eventos.publicar_movimiento(resultado, id_correlacion)
        except Exception:
            current_app.logger.exception("No se pudo procesar el aviso del movimiento.")

    return jsonify(traslado), 201


@traslados_bp.get("/traslados")
def listar_traslados():
    errores = Errores()
    page, per_page, offset = leer_paginacion(errores)
    desde, hasta = leer_rango_de_fechas(errores, request.args)
    sku = texto_opcional(errores, request.args, "sku", LARGO_SKU)
    errores.lanzar_si_hay()

    with transaccion() as cursor:
        filas, total = repo.listar(cursor, per_page, offset, sku=sku, desde=desde, hasta=hasta)
    return jsonify(respuesta_paginada(filas, page, per_page, total))


@traslados_bp.get("/traslados/<int:id_traslado>")
def obtener_traslado(id_traslado):
    with transaccion() as cursor:
        traslado = repo.obtener(cursor, id_traslado)
    if traslado is None:
        raise no_existe()
    return jsonify(traslado)
