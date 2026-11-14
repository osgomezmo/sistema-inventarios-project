"""Publicación de eventos en RabbitMQ (D8, D48).

publicar_movimiento se llama DESPUÉS del commit del movimiento. Publica
MovimientoRegistrado y, si el saldo cruzó el umbral, StockBajoUmbral. Si el
broker falla, solo deja un mensaje corto en el log: el movimiento ya está
confirmado y la respuesta HTTP no cambia.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlsplit, urlunsplit

import pika
from flask import current_app

registro = logging.getLogger(__name__)

EXCHANGE = "inventario.eventos"
PRODUCTOR = "ms-inventario"
TIMEOUT_SEGUNDOS = 2
CAMPOS_MOVIMIENTO = (
    "id_movimiento", "sku", "id_bodega", "tipo", "cantidad", "costo_unitario",
    "saldo_resultante", "costo_promedio", "valor_resultante",
)


def a_json(valor):
    """JSON en el que los Decimal salen como números exactos, sin pasar por float."""
    if isinstance(valor, dict):
        return "{" + ",".join(f"{json.dumps(str(k))}:{a_json(v)}" for k, v in valor.items()) + "}"
    if isinstance(valor, (list, tuple)):
        return "[" + ",".join(a_json(v) for v in valor) + "]"
    if isinstance(valor, Decimal):
        return format(valor, "f")
    return json.dumps(valor, ensure_ascii=False)


def fecha_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def construir_sobre(tipo, datos, id_correlacion):
    return {
        "id_evento": str(uuid.uuid4()),
        "tipo": tipo,
        "fecha": fecha_utc(),
        "productor": PRODUCTOR,
        "id_correlacion": id_correlacion,
        "datos": datos,
    }


def eventos_de(resultado):
    """[(tipo, datos)] de un resultado de aplicar_movimiento (D7, D48)."""
    movimiento = resultado["movimiento"]
    eventos = [("MovimientoRegistrado", {c: movimiento[c] for c in CAMPOS_MOVIMIENTO})]
    if resultado["cruzo_umbral"]:
        eventos.append(("StockBajoUmbral", {
            "sku": movimiento["sku"],
            "id_bodega": movimiento["id_bodega"],
            "saldo": movimiento["saldo_resultante"],
            "stock_minimo": resultado["stock_minimo"],
        }))
    return eventos


def parametros_conexion(config):
    """Parámetros de pika: RABBITMQ_URL, con el host reemplazado si hay RABBITMQ_HOST."""
    url = config["RABBITMQ_URL"]
    host = config.get("RABBITMQ_HOST")
    if host:
        partes = urlsplit(url)
        credenciales, _, servidor = partes.netloc.rpartition("@")
        puerto = f":{partes.port}" if partes.port else ""
        netloc = f"{credenciales}@{host}{puerto}" if credenciales else f"{host}{puerto}"
        url = urlunsplit(partes._replace(netloc=netloc))
    parametros = pika.URLParameters(url)
    parametros.socket_timeout = TIMEOUT_SEGUNDOS
    parametros.stack_timeout = TIMEOUT_SEGUNDOS
    parametros.blocked_connection_timeout = TIMEOUT_SEGUNDOS
    parametros.connection_attempts = 1  # un solo intento
    return parametros


def abrir_canal(config):
    """Conexión y canal con confirmación del broker. El exchange no se declara:
    solo se comprueba que exista (lo crea infra/rabbitmq/definitions.json)."""
    conexion = pika.BlockingConnection(parametros_conexion(config))
    canal = conexion.channel()
    canal.confirm_delivery()
    canal.exchange_declare(exchange=EXCHANGE, passive=True)
    return conexion, canal


def publicar_sobre(canal, sobre):
    canal.basic_publish(
        exchange=EXCHANGE,
        routing_key=sobre["tipo"],
        body=a_json(sobre).encode("utf-8"),
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,  # persistente
            message_id=sobre["id_evento"],
            correlation_id=sobre["id_correlacion"],
            type=sobre["tipo"],
        ),
    )


def publicar_movimiento(resultado, id_correlacion=None, config=None):
    """Publica los eventos del movimiento en una sola conexión.

    Nunca lanza excepciones: si algo falla, lo registra y devuelve lo publicado.
    Devuelve la lista de sobres que el broker confirmó.
    """
    config = config if config is not None else current_app.config
    movimiento = resultado["movimiento"]
    if not config.get("RABBITMQ_URL"):
        registro.info("Publicación de eventos desactivada (RABBITMQ_URL vacía); movimiento %s.",
                      movimiento["id_movimiento"])
        return []

    id_correlacion = id_correlacion or str(uuid.uuid4())
    publicados = []
    tipo = None
    try:
        conexion, canal = abrir_canal(config)
        try:
            for tipo, datos in eventos_de(resultado):
                sobre = construir_sobre(tipo, datos, id_correlacion)
                publicar_sobre(canal, sobre)
                publicados.append(sobre)
        finally:
            conexion.close()
    except Exception as error:  # el movimiento ya está confirmado (D8)
        # Sin URL, credenciales ni cuerpo: solo lo necesario para rastrearlo
        registro.warning(
            "No se publicó %s del movimiento %s (correlación %s): %s",
            tipo or "MovimientoRegistrado", movimiento["id_movimiento"], id_correlacion,
            type(error).__name__,
        )
    return publicados
