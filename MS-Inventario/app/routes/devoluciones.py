from flask import Blueprint, current_app, jsonify, request

from app import eventos
from app.clientes.productos import consultar_producto
from app.db import ejecutar_con_reintento, transaccion
from app.paginacion import leer_paginacion, respuesta_paginada
from app.repositorios import movimientos as repo_movimientos
from app.routes.movimientos import LARGO_SKU, MAX_ID, leer_id_usuario, leer_rango_de_fechas
from app.servicios.movimientos import MAX_CANTIDAD, aplicar_movimiento
from app.validacion import (
    Errores,
    decimal_obligatorio,
    entero_obligatorio,
    leer_json,
    texto_obligatorio,
    texto_opcional,
)
from app.validacion import sku as validar_sku

devoluciones_bp = Blueprint("devoluciones", __name__)

TIPO = "DEVOLUCION_CLIENTE"


def leer_cuerpo_devolucion():
    """Valida el cuerpo de POST /devoluciones-cliente; todo es obligatorio (D47)."""
    datos = leer_json()
    errores = Errores()
    campos = {
        "sku": validar_sku(errores, datos, "sku", LARGO_SKU),
        "id_bodega": entero_obligatorio(errores, datos, "id_bodega", minimo=1, maximo=MAX_ID),
        "cantidad": decimal_obligatorio(
            errores, datos, "cantidad", minimo=0, decimales=3, maximo=MAX_CANTIDAD),
        "factura_pos": texto_obligatorio(errores, datos, "factura_pos", 100),
        "motivo": texto_obligatorio(errores, datos, "motivo", 255),
    }
    if campos["cantidad"] is not None and campos["cantidad"] == 0:
        errores.agregar("cantidad", "Debe ser mayor que 0.")
    errores.lanzar_si_hay()
    return campos


@devoluciones_bp.post("/devoluciones-cliente")
def registrar_devolucion():
    id_usuario = leer_id_usuario()
    id_correlacion = (request.headers.get("X-Correlation-Id") or "").strip() or None
    campos = leer_cuerpo_devolucion()
    # Fuera de la transacción (D22).
    producto = consultar_producto(campos["sku"], id_correlacion)

    def operar():
        with transaccion() as cursor:
            # Entra al costo promedio vigente (D20); la factura del POS es la referencia.
            resultado = aplicar_movimiento(
                cursor, sku=producto["sku"], id_bodega=campos["id_bodega"], tipo=TIPO,
                cantidad=campos["cantidad"], id_usuario=id_usuario,
                unidad_medida=producto["unidad_medida"], stock_minimo=producto["stock_minimo"],
                motivo=campos["motivo"], documento_referencia=campos["factura_pos"],
            )
            resultado["respuesta"] = repo_movimientos.obtener(
                cursor, resultado["movimiento"]["id_movimiento"])
            return resultado

    resultado = ejecutar_con_reintento(operar)

    try:
        eventos.publicar_movimiento(resultado, id_correlacion)
    except Exception:
        current_app.logger.exception("No se pudo procesar el aviso del movimiento.")

    return jsonify(resultado["respuesta"]), 201


@devoluciones_bp.get("/devoluciones-cliente")
def listar_devoluciones():
    errores = Errores()
    page, per_page, offset = leer_paginacion(errores)
    desde, hasta = leer_rango_de_fechas(errores, request.args)
    sku = texto_opcional(errores, request.args, "sku", LARGO_SKU)
    errores.lanzar_si_hay()

    with transaccion() as cursor:
        filas, total = repo_movimientos.listar(
            cursor, per_page, offset, sku=sku, tipo=TIPO, desde=desde, hasta=hasta)
    return jsonify(respuesta_paginada(filas, page, per_page, total))
