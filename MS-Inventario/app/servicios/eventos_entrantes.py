"""Eventos de ms-compras que consume ms-inventario por q.inventario (D17, D18, D49).

procesar_evento valida el sobre, consulta ms-productos antes de abrir la
transacción (D22) y aplica todos los ítems en una sola transacción junto con la
fila de eventos_procesados, que hace al consumidor idempotente. Cualquier error
se lanza: el consumidor rechaza el mensaje y RabbitMQ lo reentrega.
"""

import json
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

import mysql.connector

from app.clientes.productos import consultar_producto
from app.db import ejecutar_con_reintento, transaccion
from app.servicios.movimientos import aplicar_movimiento

MERCANCIA = "MercanciaRecibida"
DEVOLUCION = "DevolucionProveedorRegistrada"
ERROR_DUPLICADO = 1062


class EventoInvalido(Exception):
    """El sobre o los datos no cumplen el contrato del evento."""


class _YaProcesado(Exception):
    """Interna: el id_evento ya estaba en eventos_procesados."""


@dataclass
class Procesamiento:
    id_evento: str
    tipo: str
    id_correlacion: str
    resultados: list = field(default_factory=list)
    ya_procesado: bool = False


def _entero_positivo(datos, campo):
    valor = datos.get(campo)
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        raise EventoInvalido(f"{campo} debe ser un entero positivo")
    return valor


def _numero(item, campo):
    valor = item.get(campo)
    if isinstance(valor, bool) or not isinstance(valor, (int, Decimal)):
        raise EventoInvalido(f"items.{campo} debe ser un número")
    return Decimal(valor)


def _texto(valor, campo, maximo, obligatorio):
    if valor is None and not obligatorio:
        return None
    if not isinstance(valor, str) or not valor.strip() or len(valor.strip()) > maximo:
        raise EventoInvalido(f"{campo} debe ser texto no vacío de máximo {maximo} caracteres")
    return valor.strip()


def leer_evento(cuerpo):
    """Valida el sobre y los datos (D49) y devuelve (sobre, datos normalizados)."""
    try:
        sobre = json.loads(cuerpo, parse_float=Decimal)
    except (ValueError, UnicodeDecodeError):
        raise EventoInvalido("el cuerpo no es JSON válido") from None
    if not isinstance(sobre, dict):
        raise EventoInvalido("el sobre debe ser un objeto")

    id_evento = sobre.get("id_evento")
    try:
        if not isinstance(id_evento, str) or str(uuid.UUID(id_evento)) != id_evento.lower():
            raise ValueError
    except ValueError:
        raise EventoInvalido("id_evento debe ser un UUID") from None
    tipo = sobre.get("tipo")
    if tipo not in (MERCANCIA, DEVOLUCION):
        raise EventoInvalido("tipo de evento no soportado")
    datos = sobre.get("datos")
    if not isinstance(datos, dict):
        raise EventoInvalido("datos debe ser un objeto")

    normalizados = {
        "id_orden": _entero_positivo(datos, "id_orden"),
        "id_bodega": _entero_positivo(datos, "id_bodega"),
        "id_usuario": _entero_positivo(datos, "id_usuario"),
        "numero": _texto(datos.get("numero"), "numero", 100, obligatorio=False),
    }
    if tipo == MERCANCIA:
        normalizados["id_recepcion"] = _entero_positivo(datos, "id_recepcion")
    else:
        normalizados["id_devolucion"] = _entero_positivo(datos, "id_devolucion")
        normalizados["motivo"] = _texto(datos.get("motivo"), "motivo", 255, obligatorio=True)

    items = datos.get("items")
    if not isinstance(items, list) or not items:
        raise EventoInvalido("items debe ser una lista no vacía")
    normalizados["items"] = []
    for item in items:
        if not isinstance(item, dict):
            raise EventoInvalido("cada ítem debe ser un objeto")
        normalizado = {
            "sku": _texto(item.get("sku"), "items.sku", 50, obligatorio=True),
            "cantidad": _numero(item, "cantidad"),
        }
        if tipo == MERCANCIA:
            normalizado["costo_unitario"] = _numero(item, "costo_unitario")
        normalizados["items"].append(normalizado)

    correlacion = sobre.get("id_correlacion")
    if not isinstance(correlacion, str) or not correlacion.strip():
        correlacion = str(uuid.uuid4())
    return {"id_evento": id_evento, "tipo": tipo, "id_correlacion": correlacion}, normalizados


def procesar_evento(cuerpo):
    """Aplica el evento y devuelve un Procesamiento con los resultados a publicar.

    Si el id_evento ya estaba procesado, no cambia nada (ya_procesado=True).
    """
    sobre, datos = leer_evento(cuerpo)
    procesamiento = Procesamiento(sobre["id_evento"], sobre["tipo"], sobre["id_correlacion"])

    # Fuera de la transacción: nunca se espera a ms-productos con filas bloqueadas (D22)
    productos = {}
    for item in datos["items"]:
        clave = item["sku"].upper()
        if clave not in productos:
            productos[clave] = consultar_producto(item["sku"], sobre["id_correlacion"])

    es_compra = sobre["tipo"] == MERCANCIA
    documento = datos["numero"] or f"OC-{datos['id_orden']}"  # D17, D19
    motivo = f"Recepción {datos['id_recepcion']}" if es_compra else datos["motivo"]

    def operar():
        with transaccion() as cursor:
            try:
                cursor.execute(
                    "INSERT INTO eventos_procesados (id_evento, tipo, procesado_en)"
                    " VALUES (%s, %s, UTC_TIMESTAMP())",
                    (sobre["id_evento"], sobre["tipo"]),
                )
            except mysql.connector.IntegrityError as error:
                if error.errno == ERROR_DUPLICADO:
                    raise _YaProcesado from None
                raise

            resultados = []
            for item in datos["items"]:
                producto = productos[item["sku"].upper()]
                resultados.append(aplicar_movimiento(
                    cursor,
                    sku=producto["sku"],  # el canónico de ms-productos (D39)
                    id_bodega=datos["id_bodega"],
                    tipo="ENTRADA_COMPRA" if es_compra else "DEVOLUCION_PROVEEDOR",
                    cantidad=item["cantidad"],
                    id_usuario=datos["id_usuario"],
                    unidad_medida=producto["unidad_medida"],
                    stock_minimo=producto["stock_minimo"],
                    costo_unitario=item.get("costo_unitario"),
                    motivo=motivo,
                    documento_referencia=documento,
                ))
            return resultados

    try:
        procesamiento.resultados = ejecutar_con_reintento(operar)
    except _YaProcesado:
        procesamiento.ya_procesado = True
    return procesamiento


def identificar(cuerpo):
    """(id_evento, tipo) para el log, aunque el cuerpo sea inválido; nunca el cuerpo."""
    try:
        sobre = json.loads(cuerpo)
        return str(sobre.get("id_evento", "-"))[:64], str(sobre.get("tipo", "-"))[:60]
    except Exception:
        return "-", "-"
