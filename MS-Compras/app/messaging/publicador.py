"""Publicador directo en RabbitMQ sobre el exchange inventario.eventos."""

from datetime import date, datetime, timezone
from decimal import Decimal
import json
from typing import Any
import uuid

from flask import current_app, g
import pika
from pika.exceptions import AMQPError

from app.config import ConfigCompras
from app.errors import ErrorAPI


class _CodificadorEvento(json.JSONEncoder):
    """Serializa Decimal y fechas dentro del sobre de eventos RabbitMQ."""

    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, datetime):
            dt_utc = o.replace(tzinfo=timezone.utc) if o.tzinfo is None else o.astimezone(timezone.utc)
            return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        if isinstance(o, date):
            return o.isoformat()
        return super().default(o)


def _construir_sobre_evento(tipo_evento: str, datos: dict[str, Any]) -> dict[str, Any]:
    """Construye el sobre estandar de evento definido en la arquitectura."""
    correlacion = getattr(g, "correlation_id", None) or str(uuid.uuid4())
    return {
        "id_evento": str(uuid.uuid4()),
        "tipo": tipo_evento,
        "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "productor": "ms-compras",
        "id_correlacion": correlacion,
        "datos": datos,
    }


def _abrir_conexion_rabbitmq(config: ConfigCompras) -> pika.BlockingConnection:
    """Abre una conexion bloqueante configurada con timeout de socket."""
    parametros = pika.URLParameters(config.rabbitmq_url)
    parametros.socket_timeout = 3.0
    parametros.blocked_connection_timeout = 3.0
    return pika.BlockingConnection(parametros)


def publicar_evento(tipo_evento: str, datos: dict[str, Any]) -> str:
    """Publica un evento durable con confirmacion de entrega del broker."""
    config: ConfigCompras = current_app.config["COMPRAS_CONFIG"]
    sobre = _construir_sobre_evento(tipo_evento, datos)
    cuerpo = json.dumps(sobre, cls=_CodificadorEvento, ensure_ascii=False)

    conexion = None
    try:
        conexion = _abrir_conexion_rabbitmq(config)
        canal = conexion.channel()
        canal.exchange_declare(
            exchange=config.rabbitmq_exchange,
            exchange_type="topic",
            durable=True,
        )
        canal.confirm_delivery()

        propiedades = pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,
            message_id=sobre["id_evento"],
            correlation_id=sobre["id_correlacion"],
            type=tipo_evento,
        )
        canal.basic_publish(
            exchange=config.rabbitmq_exchange,
            routing_key=tipo_evento,
            body=cuerpo.encode("utf-8"),
            properties=propiedades,
            mandatory=False,
        )
        return sobre["id_evento"]
    except (AMQPError, OSError, TimeoutError) as exc:
        raise ErrorAPI(
            503,
            "SERVICIO_NO_DISPONIBLE",
            "RabbitMQ no disponible para publicar eventos de compras.",
            {"evento": tipo_evento, "detalle": str(exc)},
        ) from exc
    finally:
        if conexion is not None and conexion.is_open:
            try:
                conexion.close()
            except AMQPError:
                pass


def publicar_orden_actualizada(
    id_orden: int,
    numero: str,
    id_proveedor: int,
    estado: str,
    total: Decimal | float,
) -> str:
    """Publica el evento OrdenCompraActualizada."""
    return publicar_evento(
        "OrdenCompraActualizada",
        {
            "id_orden": id_orden,
            "numero": numero,
            "id_proveedor": id_proveedor,
            "estado": estado,
            "total": total,
        },
    )


def publicar_mercancia_recibida(
    id_orden: int,
    id_recepcion: int,
    id_bodega: int,
    id_usuario: int,
    items: list[dict[str, Any]],
) -> str:
    """Publica el evento MercanciaRecibida hacia ms-inventario."""
    return publicar_evento(
        "MercanciaRecibida",
        {
            "id_orden": id_orden,
            "id_recepcion": id_recepcion,
            "id_bodega": id_bodega,
            "id_usuario": id_usuario,
            "items": items,
        },
    )


def publicar_devolucion_registrada(
    id_orden: int,
    id_devolucion: int,
    id_bodega: int,
    id_usuario: int,
    motivo: str,
    items: list[dict[str, Any]],
) -> str:
    """Publica el evento DevolucionProveedorRegistrada hacia ms-inventario."""
    return publicar_evento(
        "DevolucionProveedorRegistrada",
        {
            "id_orden": id_orden,
            "id_devolucion": id_devolucion,
            "id_bodega": id_bodega,
            "id_usuario": id_usuario,
            "motivo": motivo,
            "items": items,
        },
    )


def verificar_salud_rabbitmq() -> None:
    """Comprueba conectividad real con RabbitMQ."""
    config: ConfigCompras = current_app.config["COMPRAS_CONFIG"]
    conexion = None
    try:
        conexion = _abrir_conexion_rabbitmq(config)
        canal = conexion.channel()
        canal.close()
    except (AMQPError, OSError, TimeoutError) as exc:
        raise ErrorAPI(
            503,
            "SERVICIO_NO_DISPONIBLE",
            "RabbitMQ no disponible.",
            {"detalle": str(exc)},
        ) from exc
    finally:
        if conexion is not None and conexion.is_open:
            try:
                conexion.close()
            except AMQPError:
                pass
