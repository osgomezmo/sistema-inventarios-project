"""Pruebas del cliente HTTP de ms-productos con un servidor falso (sin MySQL).

El servidor falso corre en un hilo, en un puerto libre, registra cada petición
(ruta cruda y cabeceras) y responde lo que indique cada prueba.
"""

import json
import logging
import socket
import threading
import time
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app import create_app
from app.clientes.productos import consultar_producto
from app.errors import ApiError

TOKEN = "token-de-prueba-del-cliente"
PRODUCTO = {
    "sku": "ZZTEST-ABC",
    "nombre": "Leche entera",
    "estado": "ACTIVO",
    "unidad_medida": "KILO",
    "stock_minimo": "__DECIMAL__",
    "id_categoria": 7,
}


def cuerpo_producto(**cambios):
    """JSON del producto con stock_minimo escrito literalmente como 2.500."""
    datos = {**PRODUCTO, **cambios}
    return json.dumps(datos).replace('"__DECIMAL__"', "2.500").encode()


class ServidorFalso:
    """Responde en orden la lista de respuestas; la última se repite."""

    def __init__(self):
        self.respuestas = [(200, cuerpo_producto(), 0)]
        self.peticiones = []
        falso = self

        class Manejador(BaseHTTPRequestHandler):
            def do_GET(self):
                falso.peticiones.append({"ruta": self.path, "cabeceras": dict(self.headers)})
                indice = min(len(falso.peticiones), len(falso.respuestas)) - 1
                status, cuerpo, espera = falso.respuestas[indice]
                if espera:
                    time.sleep(espera)
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(cuerpo)))
                    self.end_headers()
                    self.wfile.write(cuerpo)
                except OSError:
                    pass  # el cliente ya cortó por timeout

            def log_message(self, *args):
                pass

        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self.servidor.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.servidor.server_port}"
        # Sondeo corto para que shutdown() no espere medio segundo por prueba.
        self.hilo = threading.Thread(
            target=self.servidor.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.hilo.start()

    def responder(self, *respuestas):
        self.respuestas = [r if len(r) == 3 else (*r, 0) for r in respuestas]

    def cerrar(self):
        self.servidor.shutdown()
        self.servidor.server_close()


@pytest.fixture
def falso():
    servidor = ServidorFalso()
    yield servidor
    servidor.cerrar()


@pytest.fixture
def app(falso):
    app = create_app({
        "TESTING": True,
        "SERVICE_TOKEN": TOKEN,
        "PRODUCTOS_URL": falso.url,
        "PRODUCTOS_TIMEOUT": 0.2,
    })
    with app.app_context():
        yield app


def puerto_cerrado():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def consultar_error(*args, **kwargs):
    with pytest.raises(ApiError) as info:
        consultar_producto(*args, **kwargs)
    return info.value


def verificar_503(error):
    assert (error.status, error.codigo) == (503, "SERVICIO_NO_DISPONIBLE")
    assert error.mensaje == "El servicio de productos no responde."


# --- Respuesta correcta ---------------------------------------------------------


def test_respuesta_correcta(app, falso):
    producto = consultar_producto("zztest-abc")
    assert producto == {
        "sku": "ZZTEST-ABC",
        "nombre": "Leche entera",
        "estado": "ACTIVO",
        "unidad_medida": "KILO",
        "stock_minimo": Decimal("2.500"),
        "id_categoria": 7,
    }
    assert isinstance(producto["stock_minimo"], Decimal)
    assert str(producto["stock_minimo"]) == "2.500"
    assert falso.peticiones[0]["ruta"] == "/productos/sku/zztest-abc"


def test_stock_minimo_entero_se_convierte_a_decimal(app, falso):
    falso.responder((200, json.dumps({**PRODUCTO, "stock_minimo": 3}).encode()))
    assert consultar_producto("ZZTEST-ABC")["stock_minimo"] == Decimal("3")


def test_producto_inactivo_se_acepta(app, falso):
    falso.responder((200, cuerpo_producto(estado="INACTIVO")))
    assert consultar_producto("ZZTEST-ABC")["estado"] == "INACTIVO"


def test_envia_token_y_correlacion(app, falso):
    consultar_producto("ZZTEST-ABC", id_correlacion="c1f4b8e2-77a0-4d1e-9a3b-0c5d6e7f8a90")
    cabeceras = falso.peticiones[0]["cabeceras"]
    assert cabeceras["Authorization"] == f"Bearer {TOKEN}"
    assert cabeceras["X-Correlation-Id"] == "c1f4b8e2-77a0-4d1e-9a3b-0c5d6e7f8a90"


def test_sin_correlacion_no_envia_la_cabecera(app, falso):
    consultar_producto("ZZTEST-ABC")
    cabeceras = {k.lower() for k in falso.peticiones[0]["cabeceras"]}
    assert "x-correlation-id" not in cabeceras
    assert "authorization" in cabeceras


def test_parametros_explicitos_reemplazan_la_configuracion(app, falso):
    consultar_producto("ZZTEST-ABC", base_url=falso.url + "/", token="otro-token", timeout=1)
    assert falso.peticiones[0]["cabeceras"]["Authorization"] == "Bearer otro-token"
    assert falso.peticiones[0]["ruta"] == "/productos/sku/ZZTEST-ABC"


def test_sku_se_codifica_en_la_ruta(app, falso):
    consultar_producto("ZZ/TEST ABC")
    ruta = falso.peticiones[0]["ruta"]
    assert ruta == "/productos/sku/ZZ%2FTEST%20ABC"


# --- 404 y reintentos -------------------------------------------------------------


def test_404_es_producto_inexistente_sin_reintento(app, falso):
    falso.responder((404, b'{"error": {}}'))
    error = consultar_error("ZZTEST-NOEXISTE")
    assert (error.status, error.codigo, error.mensaje) == (
        404, "PRODUCTO_INEXISTENTE", "El producto no existe.")
    assert len(falso.peticiones) == 1


def test_500_y_luego_200_reintenta_una_vez(app, falso):
    falso.responder((500, b"{}"), (200, cuerpo_producto()))
    assert consultar_producto("ZZTEST-ABC")["sku"] == "ZZTEST-ABC"
    assert len(falso.peticiones) == 2


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_5xx_dos_veces_da_503(app, falso, status):
    falso.responder((status, b"{}"))
    verificar_503(consultar_error("ZZTEST-ABC"))
    assert len(falso.peticiones) == 2


def test_timeout_da_503_tras_dos_intentos(app, falso):
    falso.responder((200, cuerpo_producto(), 0.6))
    inicio = time.monotonic()
    verificar_503(consultar_error("ZZTEST-ABC"))
    assert len(falso.peticiones) == 2
    assert time.monotonic() - inicio < 2  # dos timeouts de 0.2 s, no la espera completa


def test_conexion_rechazada_da_503(app):
    verificar_503(consultar_error("ZZTEST-ABC", base_url=f"http://127.0.0.1:{puerto_cerrado()}"))


@pytest.mark.parametrize("status", [400, 401, 403, 422])
def test_4xx_distinto_de_404_da_503_sin_reintento(app, falso, status):
    falso.responder((status, b'{"error": {}}'))
    verificar_503(consultar_error("ZZTEST-ABC"))
    assert len(falso.peticiones) == 1


# --- Cuerpos inválidos ------------------------------------------------------------


@pytest.mark.parametrize(
    "cuerpo",
    [
        b"<html>no es json</html>",
        b"",
        b"[1, 2, 3]",
        b'"texto"',
        json.dumps({k: v for k, v in PRODUCTO.items() if k != "stock_minimo"}).encode(),
        json.dumps({**PRODUCTO, "stock_minimo": True}).encode(),
        json.dumps({**PRODUCTO, "stock_minimo": "2.5"}).encode(),
        json.dumps({**PRODUCTO, "id_categoria": "7"}).encode(),
        json.dumps({**PRODUCTO, "stock_minimo": 1, "sku": None}).encode(),
    ],
)
def test_cuerpo_invalido_da_503(app, falso, cuerpo):
    falso.responder((200, cuerpo))
    verificar_503(consultar_error("ZZTEST-ABC"))
    assert len(falso.peticiones) == 1


# --- Seguridad de los logs ----------------------------------------------------------


@pytest.mark.parametrize("respuesta", [(500, b"{}"), (401, b"{}"), (200, b"no json")])
def test_el_token_no_aparece_en_logs_ni_errores(app, falso, caplog, respuesta):
    falso.responder(respuesta)
    with caplog.at_level(logging.DEBUG):
        error = consultar_error("ZZTEST-ABC", id_correlacion="correlacion-de-prueba")
    texto = f"{caplog.text} {error} {error.mensaje} {error.detalles}"
    assert TOKEN not in texto
    assert "Authorization" not in caplog.text
    assert falso.url not in caplog.text
    assert caplog.records  # sí quedó un mensaje corto


def test_conexion_rechazada_no_revela_la_url(app, caplog):
    url = f"http://127.0.0.1:{puerto_cerrado()}"
    with caplog.at_level(logging.DEBUG):
        error = consultar_error("ZZTEST-ABC", base_url=url)
    assert url not in caplog.text and url not in str(error)
    assert error.__cause__ is None
