"""Gancho de eventos (D8, D44).

Se invoca DESPUÉS del commit del movimiento. Por ahora solo deja un mensaje
corto en el log; más adelante publicará MovimientoRegistrado y, si el saldo
cruzó el umbral, StockBajoUmbral en RabbitMQ.
"""

import logging

registro = logging.getLogger(__name__)


def publicar_movimiento(resultado, id_correlacion=None):
    movimiento = resultado["movimiento"]
    registro.info(
        "Movimiento %s (%s) listo para publicar; cruzó el umbral: %s; correlación: %s",
        movimiento["id_movimiento"], movimiento["tipo"], resultado["cruzo_umbral"],
        id_correlacion or "-",
    )
