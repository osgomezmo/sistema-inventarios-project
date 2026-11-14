"""Pruebas de la publicación de eventos (D48).

Las unitarias usan un canal falso. La de integración publica en el RabbitMQ real
(127.0.0.1:5672) y se salta si no responde; retira de q.reportes solo su propio
mensaje y devuelve los demás.
"""

import json
import logging
import socket
import uuid
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

import pika
import pytest
from dotenv import dotenv_values

import app.eventos as eventos

CONFIG = {"RABBITMQ_URL": "amqp://usuario-de-prueba:clave-de-prueba@127.0.0.1:5672/%2F", "RABBITMQ_HOST": ""}
CAMPOS_SOBRE = {"id_evento", "tipo", "fecha", "productor", "id_correlacion", "datos"}


def resultado(cruzo_umbral=False):
    return {
        "movimiento": {
            "id_movimiento": 41, "sku": "ZZTEST-EV", "id_bodega": 3, "tipo": "SALIDA",
            "cantidad": D("2.500"), "costo_unitario": D("3150.1234"), "saldo_resultante": D("4.000"),
            "costo_promedio": D("3150.1234"), "valor_resultante": D("12600.49"), "motivo": None,
            "documento_referencia": None, "id_usuario": 7, "id_traslado": None,
            "fecha": datetime(2026, 11, 14, 12, 0, 0),
        },
        "saldo_anterior": D("6.500"),
        "stock_minimo": D("5.000"),
        "cruzo_umbral": cruzo_umbral,
    }


class CanalFalso:
    def __init__(self):
        self.publicados = []

    def basic_publish(self, exchange, routing_key, body, properties):
        self.publicados.append({"exchange": exchange, "routing_key": routing_key,
                                "cuerpo": body, "propiedades": properties})


class ConexionFalsa:
    cerrada = False

    def close(self):
        self.cerrada = True


@pytest.fixture
def canal(monkeypatch):
    canal, conexion = CanalFalso(), ConexionFalsa()
    monkeypatch.setattr(eventos, "abrir_canal", lambda config: (conexion, canal))
    canal.conexion = conexion
    return canal


def test_sobre_y_propiedades_de_movimiento_registrado(canal):
    publicados = eventos.publicar_movimiento(resultado(), "corr-1", config=CONFIG)

    assert len(publicados) == 1 and len(canal.publicados) == 1
    mensaje = canal.publicados[0]
    sobre = json.loads(mensaje["cuerpo"])
    assert set(sobre) == CAMPOS_SOBRE
    assert sobre["tipo"] == "MovimientoRegistrado" and sobre["productor"] == "ms-inventario"
    assert sobre["id_correlacion"] == "corr-1"
    assert uuid.UUID(sobre["id_evento"]).version == 4
    assert datetime.strptime(sobre["fecha"], "%Y-%m-%dT%H:%M:%SZ")
    assert (mensaje["exchange"], mensaje["routing_key"]) == ("inventario.eventos", "MovimientoRegistrado")
    propiedades = mensaje["propiedades"]
    assert propiedades.delivery_mode == 2
    assert propiedades.content_type == "application/json"
    assert propiedades.message_id == sobre["id_evento"]
    assert propiedades.correlation_id == "corr-1"
    assert canal.conexion.cerrada


def test_datos_de_movimiento_registrado_con_numeros_exactos(canal):
    eventos.publicar_movimiento(resultado(), config=CONFIG)

    cuerpo = canal.publicados[0]["cuerpo"].decode()
    datos = json.loads(cuerpo, parse_float=D)["datos"]
    assert set(datos) == set(eventos.CAMPOS_MOVIMIENTO)
    assert datos["cantidad"] == D("2.500") and datos["costo_unitario"] == D("3150.1234")
    assert datos["valor_resultante"] == D("12600.49")
    assert '"cantidad":2.500' in cuerpo  # número JSON, no texto


def test_stock_bajo_umbral_solo_si_cruzo(canal):
    eventos.publicar_movimiento(resultado(cruzo_umbral=False), config=CONFIG)
    assert [m["routing_key"] for m in canal.publicados] == ["MovimientoRegistrado"]

    canal.publicados.clear()
    eventos.publicar_movimiento(resultado(cruzo_umbral=True), "corr-2", config=CONFIG)
    assert [m["routing_key"] for m in canal.publicados] == ["MovimientoRegistrado", "StockBajoUmbral"]
    umbral = json.loads(canal.publicados[1]["cuerpo"], parse_float=D)
    assert umbral["datos"] == {"sku": "ZZTEST-EV", "id_bodega": 3, "saldo": D("4.000"), "stock_minimo": D("5.000")}
    assert umbral["id_correlacion"] == "corr-2"


def test_sin_correlacion_se_genera_una(canal):
    eventos.publicar_movimiento(resultado(cruzo_umbral=True), config=CONFIG)

    correlaciones = {json.loads(m["cuerpo"])["id_correlacion"] for m in canal.publicados}
    assert len(correlaciones) == 1  # la misma para los dos eventos
    assert uuid.UUID(correlaciones.pop()).version == 4


def test_falla_de_conexion_no_lanza_y_no_revela_credenciales(monkeypatch, caplog):
    def falla(config):
        raise pika.exceptions.AMQPConnectionError("conexión rechazada a " + config["RABBITMQ_URL"])

    monkeypatch.setattr(eventos, "abrir_canal", falla)
    with caplog.at_level(logging.WARNING):
        assert eventos.publicar_movimiento(resultado(), "corr-3", config=CONFIG) == []

    assert "AMQPConnectionError" in caplog.text and "41" in caplog.text and "corr-3" in caplog.text
    assert "clave-de-prueba" not in caplog.text and "usuario-de-prueba" not in caplog.text


def test_url_vacia_no_intenta_conectar(monkeypatch, caplog):
    def no_debe_llamarse(config):
        raise AssertionError("no debe conectarse")

    monkeypatch.setattr(eventos, "abrir_canal", no_debe_llamarse)
    with caplog.at_level(logging.INFO):
        assert eventos.publicar_movimiento(resultado(), config={"RABBITMQ_URL": ""}) == []
    assert "desactivada" in caplog.text


def test_rabbitmq_host_reemplaza_el_host_y_conserva_credenciales():
    parametros = eventos.parametros_conexion(
        {"RABBITMQ_URL": "amqp://u:p%40x@127.0.0.1:5672/%2F", "RABBITMQ_HOST": "rabbitmq-inventario"})
    assert (parametros.host, parametros.port, parametros.virtual_host) == ("rabbitmq-inventario", 5672, "/")
    assert parametros.credentials.username == "u" and parametros.credentials.password == "p@x"
    assert parametros.connection_attempts == 1 and parametros.socket_timeout == 2


# --- Integración con el broker real -------------------------------------------------


def url_real():
    url = dotenv_values(Path(__file__).resolve().parent.parent / ".env").get("RABBITMQ_URL")
    try:
        socket.create_connection(("127.0.0.1", 5672), timeout=1).close()
    except OSError:
        return None
    return url or None


def test_integracion_el_evento_llega_a_q_reportes():
    url = url_real()
    if url is None:
        pytest.skip("RabbitMQ no disponible en 127.0.0.1:5672 o sin RABBITMQ_URL")

    publicados = eventos.publicar_movimiento(resultado(), "corr-integracion",
                                             config={"RABBITMQ_URL": url, "RABBITMQ_HOST": ""})
    assert len(publicados) == 1
    mio = publicados[0]["id_evento"]

    conexion = pika.BlockingConnection(pika.URLParameters(url))
    canal = conexion.channel()
    encontrado, ajenos = None, []
    try:
        for _ in range(1000):
            metodo, propiedades, cuerpo = canal.basic_get("q.reportes", auto_ack=False)
            if metodo is None:
                break
            if propiedades.message_id == mio:
                encontrado = json.loads(cuerpo, parse_float=D)
                canal.basic_ack(metodo.delivery_tag)  # se retira solo el de la prueba
                break
            ajenos.append(metodo.delivery_tag)
    finally:
        for etiqueta in ajenos:
            canal.basic_nack(etiqueta, requeue=True)  # los demás vuelven a la cola
        conexion.close()

    assert encontrado is not None
    assert encontrado["tipo"] == "MovimientoRegistrado"
    assert encontrado["datos"]["cantidad"] == D("2.500")
    assert encontrado["id_correlacion"] == "corr-integracion"
