"""Ruta global de consulta de devoluciones a proveedores."""

from flask import Blueprint, jsonify

from app.auth import requiere_roles
from app.paginacion import construir_meta, obtener_parametros_paginacion
from app.repositorios.devoluciones import listar_devoluciones
from app.validacion import parsear_filtros_fecha_y_proveedor

devoluciones_bp = Blueprint(
    "devoluciones",
    __name__,
    url_prefix="/devoluciones-proveedor",
)


@devoluciones_bp.get("")
@requiere_roles("admin", "jefe_bodega", "compras")
def ruta_listar_devoluciones():
    """Lista devoluciones a proveedores filtradas por proveedor y rango de fechas."""
    page, per_page, offset = obtener_parametros_paginacion()
    id_proveedor, desde, hasta = parsear_filtros_fecha_y_proveedor()

    devoluciones, total = listar_devoluciones(
        id_proveedor=id_proveedor,
        desde=desde,
        hasta=hasta,
        limite=per_page,
        offset=offset,
    )
    return jsonify({"data": devoluciones, "meta": construir_meta(total, page, per_page)}), 200
