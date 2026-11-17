"""Pruebas de manejar (D49) con un canal falso, sin broker ni MySQL."""

import json
import logging
from types import SimpleNamespace

import pytest

import app.consumidor as consumidor
from app.servicios.eventos_entrantes import Procesamiento

ID_EVENTO = "e2e00000-0000-4000-8000-0000000000aa"
CUERPO = json.dumps({"id_evento": ID_EVENTO, "tipo": "MercanciaRecibida"}).encode()


class CanalFalso:
    def __init__(self):
        self.acks, self.nacks = [], []

    def basic_ack(self, delivery_tag):
        self.acks.append(delivery_tag)

    def basic_nack(self, delivery_tag, requeue):
        self.nacks.append((delivery_tag, requeue))


def propiedades(headers):
    return SimpleNamespace(headers=headers)


@pytest.fixture
def canal():
    return CanalFalso()


@pytest.fixture
def falla(monkeypatch):
    def procesar(cuerpo):
        raise RuntimeError("falla de prueba")

    monkeypatch.setattr(consumidor, "procesar_evento", procesar)


def manejar(canal, headers):
    consumidor.manejar(canal, SimpleNamespace(delivery_tag=7), propiedades(headers), CUERPO, {})


@pytest.mark.parametrize("intento", [0, 1, 2])
def test_antes_del_limite_reencola(canal, falla, intento):
    manejar(canal, {"x-acquired-count": intento})
    assert canal.nacks == [(7, True)] and canal.acks == []


@pytest.mark.parametrize("intento", [3, 4, 3545])
def test_desde_el_limite_va_a_la_cola_de_errores(canal, falla, intento, caplog):
    with caplog.at_level(logging.ERROR):
        manejar(canal, {"x-acquired-count": intento})
    assert canal.nacks == [(7, False)] and canal.acks == []
    assert ID_EVENTO in caplog.text and f"intento {intento}" in caplog.text
    assert "RuntimeError" in caplog.text


@pytest.mark.parametrize("headers", [None, {}])
def test_sin_cabeceras_cuenta_como_cero(canal, falla, headers):
    manejar(canal, headers)
    assert canal.nacks == [(7, True)]


def test_usa_x_delivery_count_si_no_hay_x_acquired_count(canal, falla):
    manejar(canal, {"x-delivery-count": 3})
    assert canal.nacks == [(7, False)]


def test_x_acquired_count_tiene_prioridad(canal, falla):
    manejar(canal, {"x-acquired-count": 0, "x-delivery-count": 5})
    assert canal.nacks == [(7, True)]


def test_evento_correcto_hace_ack(canal, monkeypatch):
    publicados = []
    monkeypatch.setattr(consumidor, "procesar_evento", lambda cuerpo: Procesamiento(
        ID_EVENTO, "MercanciaRecibida", "corr-1", resultados=[{"r": 1}]))
    monkeypatch.setattr(consumidor, "publicar_movimiento",
                        lambda resultado, correlacion, config: publicados.append(correlacion))

    manejar(canal, {"x-acquired-count": 5})

    assert canal.acks == [7] and canal.nacks == []
    assert publicados == ["corr-1"]


def test_evento_ya_procesado_hace_ack_sin_publicar(canal, monkeypatch):
    monkeypatch.setattr(consumidor, "procesar_evento", lambda cuerpo: Procesamiento(
        ID_EVENTO, "MercanciaRecibida", "corr-1", ya_procesado=True))
    monkeypatch.setattr(consumidor, "publicar_movimiento",
                        lambda *a: pytest.fail("no debe publicar"))

    manejar(canal, None)

    assert canal.acks == [7] and canal.nacks == []
