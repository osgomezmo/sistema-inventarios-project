"""Validadores de carga JSON, decimales financieros/cantidad y filtros."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from flask import request

from app.errors import ErrorAPI

ESTADOS_ORDEN = {"BORRADOR", "APROBADA", "RECIBIDA_PARCIAL", "RECIBIDA", "ANULADA"}


def obtener_json() -> dict[str, Any]:
    """Obtiene y valida que el cuerpo HTTP sea un objeto JSON."""
    cuerpo = request.get_json(silent=True)
    if not isinstance(cuerpo, dict):
        raise ErrorAPI(
            400,
            "VALIDACION",
            "El cuerpo de la peticion debe ser un objeto JSON valido.",
        )
    return cuerpo


MAX_INT32 = 2_147_483_647


def _entero_positivo(valor: Any, campo: str, errores: dict[str, str]) -> int | None:
    if isinstance(valor, bool) or isinstance(valor, float):
        errores[campo] = "Debe ser un numero entero positivo."
        return None
    if isinstance(valor, int):
        valor_int = valor
    elif isinstance(valor, str) and valor.strip().isdigit():
        valor_int = int(valor.strip())
    else:
        errores[campo] = "Debe ser un numero entero positivo."
        return None

    if valor_int <= 0 or valor_int > MAX_INT32:
        errores[campo] = f"Debe ser un entero entre 1 y {MAX_INT32}."
        return None
    return valor_int


def _decimal_positivo(
    valor: Any, campo: str, escala: int, errores: dict[str, str]
) -> Decimal | None:
    if valor is None or isinstance(valor, bool):
        errores[campo] = "Debe ser un numero positivo."
        return None
    try:
        dec = Decimal(str(valor).strip())
    except (InvalidOperation, ValueError):
        errores[campo] = "Formato numerico invalido."
        return None

    maximo = Decimal(10 ** (14 - escala)) - Decimal(f"0.{'0' * (escala - 1)}1") if escala > 0 else Decimal(10**14 - 1)
    if not dec.is_finite() or dec <= Decimal("0") or dec > maximo:
        errores[campo] = "Valor fuera de rango permitido."
        return None

    cuantizador = Decimal("1") if escala == 0 else Decimal(f"1.{'0' * escala}")
    cuantizado = dec.quantize(cuantizador, rounding=ROUND_HALF_UP)
    if cuantizado <= Decimal("0"):
        errores[campo] = f"Debe ser mayor que cero (minimo {Decimal('10') ** (-escala)})."
        return None
    return cuantizado


def _texto_requerido(
    valor: Any, campo: str, max_len: int, errores: dict[str, str]
) -> str | None:
    if not isinstance(valor, str) or not valor.strip():
        errores[campo] = "Campo obligatorio."
        return None
    limpio = valor.strip()
    if len(limpio) > max_len:
        errores[campo] = f"No debe superar {max_len} caracteres."
        return None
    return limpio


def _texto_opcional(
    valor: Any, campo: str, max_len: int, errores: dict[str, str], defecto: str = ""
) -> str:
    if valor is None:
        return defecto
    if not isinstance(valor, str):
        errores[campo] = "Debe ser una cadena de texto."
        return defecto
    limpio = valor.strip()
    if len(limpio) > max_len:
        errores[campo] = f"No debe superar {max_len} caracteres."
        return defecto
    return limpio


def parsear_fecha_filtro(valor: str | None, nombre: str, fin_de_dia: bool) -> datetime | None:
    """Convierte parametros de query desde/hasta (YYYY-MM-DD o ISO) a datetime UTC."""
    if not valor or not valor.strip():
        return None
    bruto = valor.strip()

    if len(bruto) == 10:
        try:
            fecha = datetime.strptime(bruto, "%Y-%m-%d")
        except ValueError as exc:
            raise ErrorAPI(
                400,
                "VALIDACION",
                f"Formato invalido para {nombre}; use YYYY-MM-DD o ISO-8601.",
            ) from exc
        if fin_de_dia:
            return fecha.replace(hour=23, minute=59, second=59)
        return fecha.replace(hour=0, minute=0, second=0)

    try:
        iso = bruto.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
    except ValueError as exc:
        raise ErrorAPI(
            400,
            "VALIDACION",
            f"Formato invalido para {nombre}; use YYYY-MM-DD o ISO-8601.",
        ) from exc

    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def validar_orden_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Valida creacion o actualizacion de orden de compra."""
    errores: dict[str, str] = {}

    id_proveedor = _entero_positivo(data.get("id_proveedor"), "id_proveedor", errores)
    id_bodega_destino = _entero_positivo(
        data.get("id_bodega_destino"), "id_bodega_destino", errores
    )

    items_raw = data.get("items")
    if not isinstance(items_raw, list) or len(items_raw) == 0:
        errores["items"] = "Debe incluir al menos un item en la orden."
        items_raw = []

    items_limpios: list[dict[str, Any]] = []
    skus_vistos: set[str] = set()

    for idx, item in enumerate(items_raw):
        prefijo = f"items[{idx}]"
        if not isinstance(item, dict):
            errores[prefijo] = "Cada item debe ser un objeto."
            continue

        sku = _texto_requerido(item.get("sku"), f"{prefijo}.sku", 50, errores)
        if sku:
            sku_norm = sku.upper()
            if sku_norm in skus_vistos:
                errores[f"{prefijo}.sku"] = "SKU duplicado dentro de la misma orden."
            else:
                skus_vistos.add(sku_norm)
            sku = sku_norm

        cantidad_bruta = (
            item.get("cantidad")
            if "cantidad" in item
            else item.get("cantidad_pedida")
        )
        cantidad = _decimal_positivo(cantidad_bruta, f"{prefijo}.cantidad", 3, errores)
        precio = _decimal_positivo(
            item.get("precio_unitario"), f"{prefijo}.precio_unitario", 2, errores
        )

        if sku and cantidad is not None and precio is not None:
            items_limpios.append(
                {
                    "sku": sku,
                    "cantidad_pedida": cantidad,
                    "precio_unitario": precio,
                }
            )

    if errores:
        raise ErrorAPI(422, "VALIDACION", "Datos de orden de compra invalidos.", errores)

    return {
        "id_proveedor": id_proveedor,
        "id_bodega_destino": id_bodega_destino,
        "items": items_limpios,
    }


def validar_anulacion_payload(data: dict[str, Any]) -> str:
    """Valida el motivo obligatorio al anular una orden de compra."""
    errores: dict[str, str] = {}
    motivo = _texto_requerido(data.get("motivo"), "motivo", 255, errores)
    if errores or not motivo:
        raise ErrorAPI(422, "VALIDACION", "El motivo de anulacion es obligatorio.", errores)
    return motivo


def validar_recepcion_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Valida el cuerpo de registro de recepcion de mercancia."""
    errores: dict[str, str] = {}
    observaciones = _texto_opcional(
        data.get("observaciones"), "observaciones", 300, errores, defecto=""
    )

    items_raw = data.get("items")
    if not isinstance(items_raw, list) or len(items_raw) == 0:
        errores["items"] = "Debe especificar al menos una linea recibida."
        items_raw = []

    items_limpios: list[dict[str, Any]] = []
    detalles_vistos: set[int] = set()

    for idx, item in enumerate(items_raw):
        prefijo = f"items[{idx}]"
        if not isinstance(item, dict):
            errores[prefijo] = "Cada item debe ser un objeto."
            continue

        id_detalle = _entero_positivo(item.get("id_detalle"), f"{prefijo}.id_detalle", errores)
        if id_detalle is not None:
            if id_detalle in detalles_vistos:
                errores[f"{prefijo}.id_detalle"] = "id_detalle duplicado en la recepcion."
            else:
                detalles_vistos.add(id_detalle)

        cantidad = _decimal_positivo(item.get("cantidad"), f"{prefijo}.cantidad", 3, errores)
        if id_detalle is not None and cantidad is not None:
            items_limpios.append({"id_detalle": id_detalle, "cantidad": cantidad})

    if errores:
        raise ErrorAPI(422, "VALIDACION", "Datos de recepcion invalidos.", errores)

    return {"observaciones": observaciones, "items": items_limpios}


def validar_devolucion_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Valida el cuerpo de registro de devolucion a proveedor."""
    errores: dict[str, str] = {}
    motivo = _texto_requerido(data.get("motivo"), "motivo", 255, errores)

    items_raw = data.get("items")
    if not isinstance(items_raw, list) or len(items_raw) == 0:
        errores["items"] = "Debe especificar al menos un item a devolver."
        items_raw = []

    items_limpios: list[dict[str, Any]] = []
    detalles_vistos: set[int] = set()

    for idx, item in enumerate(items_raw):
        prefijo = f"items[{idx}]"
        if not isinstance(item, dict):
            errores[prefijo] = "Cada item debe ser un objeto."
            continue

        id_detalle = _entero_positivo(item.get("id_detalle"), f"{prefijo}.id_detalle", errores)
        if id_detalle is not None:
            if id_detalle in detalles_vistos:
                errores[f"{prefijo}.id_detalle"] = "id_detalle duplicado en la devolucion."
            else:
                detalles_vistos.add(id_detalle)

        cantidad = _decimal_positivo(item.get("cantidad"), f"{prefijo}.cantidad", 3, errores)
        if id_detalle is not None and cantidad is not None:
            items_limpios.append({"id_detalle": id_detalle, "cantidad": cantidad})

    if errores:
        raise ErrorAPI(422, "VALIDACION", "Datos de devolucion invalidos.", errores)

    return {"motivo": motivo, "items": items_limpios}


def parsear_filtros_fecha_y_proveedor() -> tuple[int | None, datetime | None, datetime | None]:
    """Extrae y valida los query params compartidos id_proveedor, desde y hasta."""
    id_prov_raw = (request.args.get("id_proveedor") or "").strip()
    id_proveedor: int | None = None
    if id_prov_raw:
        try:
            id_proveedor = int(id_prov_raw)
        except ValueError as exc:
            raise ErrorAPI(
                400,
                "VALIDACION",
                "El parametro id_proveedor debe ser un entero positivo.",
            ) from exc
        if id_proveedor <= 0:
            raise ErrorAPI(
                400,
                "VALIDACION",
                "El parametro id_proveedor debe ser mayor que cero.",
            )

    desde = parsear_fecha_filtro(request.args.get("desde"), "desde", fin_de_dia=False)
    hasta = parsear_fecha_filtro(request.args.get("hasta"), "hasta", fin_de_dia=True)
    if desde is not None and hasta is not None and desde > hasta:
        raise ErrorAPI(
            400,
            "VALIDACION",
            "La fecha desde no puede ser posterior a hasta.",
        )

    return id_proveedor, desde, hasta

