"""Consumidor RabbitMQ para la cola q.reportes con pika.

Consume eventos de negocio de inventario (MovimientoRegistrado,
OrdenCompraActualizada, StockBajoUmbral) y actualiza el modelo relacional
optimizado para reportes.
"""

import json
import logging
import sys
import threading
import time

import pika

from app.config import cargar_configuracion
from app.repositorios.eventos_repo import procesar_evento

logger = logging.getLogger("consumidor_reportes")
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [consumidor] %(message)s",
)

COLA_REPORTES = "q.reportes"
_consumidor_hilo = None
_detener_evento = threading.Event()


def procesar_mensaje_amqp(ch, method, properties, body):
    """Callback invocado al recibir un mensaje desde q.reportes."""
    try:
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as json_err:
            logger.error("Payload recibido no es un JSON válido: %s", json_err)
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=True)
            return

        resultado = procesar_evento(payload)
        if resultado.get("duplicado"):
            logger.info("Evento duplicado omitido (id_evento=%s)", payload.get("id_evento"))
        else:
            logger.info(
                "Evento procesado exitosamente (tipo=%s, id_evento=%s)",
                payload.get("tipo"),
                payload.get("id_evento"),
            )

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as err:
        logger.error("Error al procesar mensaje en q.reportes: %s", err, exc_info=True)
        # basic_reject con requeue=True para que la Quorum Queue incremente x-delivery-count
        # y tras 3 intentos (x-delivery-limit: 3) RabbitMQ lo transfiera a q.reportes.errores
        ch.basic_reject(delivery_tag=method.delivery_tag, requeue=True)


def iniciar_consumidor(config=None, detener_flag=None):
    """Inicia el bucle de consumo de RabbitMQ."""
    cfg = config if config is not None else cargar_configuracion()
    url = cfg.get("RABBITMQ_URL")
    if not url:
        logger.error("RABBITMQ_URL no está configurada.")
        return

    while detener_flag is None or not detener_flag.is_set():
        try:
            logger.info("Conectando consumidor a RabbitMQ en q.reportes...")
            params = pika.URLParameters(url)
            params.heartbeat = 60
            params.blocked_connection_timeout = 30
            conexion = pika.BlockingConnection(params)
            canal = conexion.channel()

            canal.basic_qos(prefetch_count=1)
            canal.basic_consume(
                queue=COLA_REPORTES,
                on_message_callback=procesar_mensaje_amqp,
                auto_ack=False,
            )

            logger.info("Consumidor listo y escuchando en '%s'.", COLA_REPORTES)

            while canal.is_open and (detener_flag is None or not detener_flag.is_set()):
                conexion.process_data_events(time_limit=1)

            if canal.is_open:
                canal.close()
            if conexion.is_open:
                conexion.close()
            break

        except (pika.exceptions.AMQPConnectionError, pika.exceptions.ChannelError) as conn_err:
            logger.warning("Fallo en conexión con RabbitMQ: %s. Reintentando en 3s...", conn_err)
            time.sleep(3)
        except Exception as ex:
            logger.error("Excepción inesperada en consumidor: %s", ex, exc_info=True)
            time.sleep(3)


def iniciar_consumidor_en_hilo(app=None):
    """Lanza el consumidor en un hilo secundario tipo daemon."""
    global _consumidor_hilo, _detener_evento
    if _consumidor_hilo is not None and _consumidor_hilo.is_alive():
        return _consumidor_hilo

    _detener_evento.clear()
    cfg = app.config if app is not None else None
    _consumidor_hilo = threading.Thread(
        target=iniciar_consumidor,
        args=(cfg, _detener_evento),
        daemon=True,
        name="HiloConsumidorReportes",
    )
    _consumidor_hilo.start()
    return _consumidor_hilo


def detener_consumidor():
    """Señala al consumidor para que termine limpiamente."""
    global _detener_evento
    _detener_evento.set()


def main():
    try:
        iniciar_consumidor()
    except KeyboardInterrupt:
        logger.info("Consumidor detenido por el usuario.")
        sys.exit(0)


if __name__ == "__main__":
    main()
