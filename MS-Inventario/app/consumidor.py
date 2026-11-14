"""Consumidor de q.inventario (D49): python -m app.consumidor

Prefetch 1 y ack manual. Confirma solo después de guardar el efecto y publicar
los eventos resultantes; ante cualquier error rechaza con reentrega, y al
superar x-delivery-limit RabbitMQ lleva el mensaje a q.inventario.errores (D18).
"""

import logging
import time

import pika

from app import create_app
from app.eventos import parametros_conexion, publicar_movimiento
from app.servicios.eventos_entrantes import identificar, procesar_evento

COLA = "q.inventario"
ESPERA_RECONEXION = 5

registro = logging.getLogger("app.consumidor")


def manejar(canal, metodo, propiedades, cuerpo, config):
    """Procesa un mensaje y lo confirma o lo rechaza."""
    id_evento, tipo = identificar(cuerpo)
    intento = (propiedades.headers or {}).get("x-delivery-count", 0)
    try:
        procesamiento = procesar_evento(cuerpo)
    except Exception as error:
        # Sin el cuerpo: solo lo necesario para rastrear el mensaje
        registro.warning("Evento %s (%s) rechazado en el intento %s: %s",
                         id_evento, tipo, intento, type(error).__name__)
        canal.basic_nack(delivery_tag=metodo.delivery_tag, requeue=True)
        return

    if procesamiento.ya_procesado:
        registro.info("Evento %s (%s) ya estaba procesado; se confirma sin aplicarlo.", id_evento, tipo)
    else:
        # Después del commit (D8), con la correlación del evento (D17)
        for resultado in procesamiento.resultados:
            publicar_movimiento(resultado, procesamiento.id_correlacion, config)
        registro.info("Evento %s (%s) aplicado: %s movimientos.", id_evento, tipo,
                      len(procesamiento.resultados))
    canal.basic_ack(delivery_tag=metodo.delivery_tag)


def consumir(config):
    """Una sesión de consumo; termina con excepción si se cae la conexión."""
    parametros = parametros_conexion(config)
    parametros.socket_timeout = 10
    parametros.heartbeat = 30
    conexion = pika.BlockingConnection(parametros)
    try:
        canal = conexion.channel()
        canal.basic_qos(prefetch_count=1)
        canal.basic_consume(
            queue=COLA,
            on_message_callback=lambda c, m, p, b: manejar(c, m, p, b, config),
            auto_ack=False,
        )
        registro.info("Consumidor escuchando %s.", COLA)
        canal.start_consuming()
    finally:
        if conexion.is_open:
            conexion.close()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = create_app()
    with app.app_context():
        if not app.config.get("RABBITMQ_URL"):
            registro.error("RABBITMQ_URL vacía: el consumidor no puede arrancar.")
            raise SystemExit(1)
        while True:
            try:
                consumir(app.config)
            except KeyboardInterrupt:
                break
            except Exception as error:
                # Sin URL ni credenciales en el log
                registro.warning("Conexión con RabbitMQ perdida (%s); reintento en %s s.",
                                 type(error).__name__, ESPERA_RECONEXION)
                time.sleep(ESPERA_RECONEXION)


if __name__ == "__main__":
    main()
