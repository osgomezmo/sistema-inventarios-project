"""Rutas REST de ordenes de compra, recepciones y devoluciones por orden."""

from flask import Blueprint, g, jsonify, request

from app.auth import requiere_roles
from app.errors import ErrorAPI
from app.paginacion import construir_meta, obtener_parametros_paginacion
from app.repositorios.devoluciones import registrar_devolucion
from app.repositorios.ordenes import (
    actualizar_orden_borrador,
    anular_orden,
    aprobar_orden,
    crear_orden_compra,
    listar_ordenes,
    obtener_orden_por_id,
)
from app.repositorios.recepciones import (
    listar_recepciones_por_orden,
    registrar_recepcion,
)
from app.validacion import (
    ESTADOS_ORDEN,
    obtener_json,
    parsear_filtros_fecha_y_proveedor,
    validar_anulacion_payload,
    validar_devolucion_payload,
    validar_orden_payload,
    validar_recepcion_payload,
)

ordenes_bp = Blueprint("ordenes", __name__, url_prefix="/ordenes-compra")


@ordenes_bp.get("")
@requiere_roles("admin", "jefe_bodega", "compras", "gerente")
def ruta_listar_ordenes():
    """Lista ordenes de compra paginadas con filtros opcionales."""
    page, per_page, offset = obtener_parametros_paginacion()
    id_proveedor, desde, hasta = parsear_filtros_fecha_y_proveedor()

    estado_raw = (request.args.get("estado") or "").strip().upper()
    estado: str | None = None
    if estado_raw:
        if estado_raw not in ESTADOS_ORDEN:
            raise ErrorAPI(
                422,
                "VALIDACION",
                "Estado de orden invalido.",
                {"estados_permitidos": sorted(ESTADOS_ORDEN)},
            )
        estado = estado_raw

    ordenes, total = listar_ordenes(
        estado=estado,
        id_proveedor=id_proveedor,
        desde=desde,
        hasta=hasta,
        limite=per_page,
        offset=offset,
    )
    return jsonify({"data": ordenes, "meta": construir_meta(total, page, per_page)}), 200


@ordenes_bp.get("/<int:id_orden>")
@requiere_roles("admin", "jefe_bodega", "compras", "gerente")
def ruta_obtener_orden(id_orden: int):
    """Obtiene el detalle completo de una orden de compra."""
    return jsonify(obtener_orden_por_id(id_orden)), 200


@ordenes_bp.post("")
@requiere_roles("admin", "compras")
def ruta_crear_orden():
    """Crea una nueva orden de compra en estado BORRADOR."""
    payload = validar_orden_payload(obtener_json())
    creada = crear_orden_compra(payload, g.usuario_id)
    return jsonify(creada), 201


@ordenes_bp.put("/<int:id_orden>")
@requiere_roles("admin", "compras")
def ruta_actualizar_orden(id_orden: int):
    """Actualiza una orden de compra existente en estado BORRADOR."""
    payload = validar_orden_payload(obtener_json())
    actualizada = actualizar_orden_borrador(id_orden, payload)
    return jsonify(actualizada), 200


@ordenes_bp.post("/<int:id_orden>/aprobar")
@requiere_roles("admin", "gerente")
def ruta_aprobar_orden(id_orden: int):
    """Aprueba una orden de compra (BORRADOR -> APROBADA)."""
    aprobada = aprobar_orden(id_orden, g.usuario_id)
    return jsonify(aprobada), 200


@ordenes_bp.post("/<int:id_orden>/anular")
@requiere_roles("admin", "gerente")
def ruta_anular_orden(id_orden: int):
    """Anula una orden de compra sin recepciones registradas."""
    motivo = validar_anulacion_payload(obtener_json())
    anulada = anular_orden(id_orden, motivo)
    return jsonify(anulada), 200


@ordenes_bp.post("/<int:id_orden>/recepciones")
@requiere_roles("admin", "jefe_bodega")
def ruta_registrar_recepcion(id_orden: int):
    """Registra una recepcion parcial o total sobre una orden aprobada."""
    payload = validar_recepcion_payload(obtener_json())
    recepcion = registrar_recepcion(id_orden, payload, g.usuario_id)
    return jsonify(recepcion), 201


@ordenes_bp.get("/<int:id_orden>/recepciones")
@requiere_roles("admin", "jefe_bodega", "compras", "gerente")
def ruta_listar_recepciones_orden(id_orden: int):
    """Lista las recepciones asociadas a una orden de compra."""
    return jsonify(listar_recepciones_por_orden(id_orden)), 200


@ordenes_bp.post("/<int:id_orden>/devoluciones")
@requiere_roles("admin", "jefe_bodega", "compras")
def ruta_registrar_devolucion(id_orden: int):
    """Registra una devolucion al proveedor sobre mercancia previamente recibida."""
    payload = validar_devolucion_payload(obtener_json())
    devolucion = registrar_devolucion(id_orden, payload, g.usuario_id)
    return jsonify(devolucion), 201
