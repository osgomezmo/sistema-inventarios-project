"""Pruebas unitarias de cliente HTTP a ms-proveedores y publicador RabbitMQ."""

from decimal import Decimal
import json
from unittest.mock import MagicMock

from pika.exceptions import AMQPConnectionError
import pytest
import requests

from app.clientes.proveedores import validar_proveedor_activo
from app.errors import ErrorAPI
from app.messaging.publicador import (
    publicar_devolucion_registrada,
    publicar_mercancia_recibida,
    publicar_orden_actualizada,
)


class TestClienteProveedores:
    def test_acepta_proveedor_activo_y_propaga_headers(self, app, monkeypatch):
        respuesta = MagicMock()
        respuesta.status_code = 200
        respuesta.json.return_value = {
            "id_proveedor": 5,
            "razon_social": "Insumos ABC",
            "estado": "ACTIVO",
        }
        capturado = {}

        def fake_get(url, headers, timeout):
            capturado["url"] = url
            capturado["headers"] = headers
            capturado["timeout"] = timeout
            return respuesta

        monkeypatch.setattr("app.clientes.proveedores.requests.get", fake_get)

        with app.test_request_context("/ordenes-compra"):
            from flask import g

            g.usuario_id = 12
            g.usuario_rol = "compras"
            g.correlation_id = "corr-prov-1"

            proveedor = validar_proveedor_activo(5)

        assert proveedor["estado"] == "ACTIVO"
        assert capturado["url"] == "http://proveedores.local:3000/proveedores/5"
        assert capturado["headers"]["X-Correlation-Id"] == "corr-prov-1"
        assert capturado["headers"]["Authorization"].startswith("Bearer ")
        assert capturado["timeout"] == 1.5

    def test_rechaza_proveedor_inactivo_y_proveedor_inexistente(self, app, monkeypatch):
        resp_inactivo = MagicMock()
        resp_inactivo.status_code = 200
        resp_inactivo.json.return_value = {"id_proveedor": 5, "estado": "INACTIVO"}
        monkeypatch.setattr("app.clientes.proveedores.requests.get", lambda *a, **k: resp_inactivo)

        with app.test_request_context("/ordenes-compra"):
            with pytest.raises(ErrorAPI) as exc_inact:
                validar_proveedor_activo(5)
            assert exc_inact.value.status_code == 422
            assert exc_inact.value.codigo == "PROVEEDOR_INACTIVO"

        resp_404 = MagicMock()
        resp_404.status_code = 404
        monkeypatch.setattr("app.clientes.proveedores.requests.get", lambda *a, **k: resp_404)

        with app.test_request_context("/ordenes-compra"):
            with pytest.raises(ErrorAPI) as exc_404:
                validar_proveedor_activo(999)
            assert exc_404.value.status_code == 422
            assert exc_404.value.codigo == "PROVEEDOR_NO_EXISTE"

    def test_traduce_timeout_error_red_500_y_json_corrupto_a_503(self, app, monkeypatch):
        def lanzar_timeout(*_args, **_kwargs):
            raise requests.Timeout("timeout simulado")

        monkeypatch.setattr("app.clientes.proveedores.requests.get", lanzar_timeout)
        with app.test_request_context("/ordenes-compra"):
            with pytest.raises(ErrorAPI) as exc_to:
                validar_proveedor_activo(1)
            assert exc_to.value.status_code == 503
            assert exc_to.value.codigo == "SERVICIO_NO_DISPONIBLE"

        resp_bad_json = MagicMock()
        resp_bad_json.status_code = 200
        resp_bad_json.json.side_effect = ValueError("No es JSON")
        monkeypatch.setattr("app.clientes.proveedores.requests.get", lambda *a, **k: resp_bad_json)
        with app.test_request_context("/ordenes-compra"):
            with pytest.raises(ErrorAPI) as exc_json:
                validar_proveedor_activo(1)
            assert exc_json.value.status_code == 503


class TestPublicadorRabbitMQ:
    def test_publica_eventos_con_sobre_confirm_delivery_y_delivery_mode_2(self, app, monkeypatch):
        canal = MagicMock()
        conexion = MagicMock()
        conexion.channel.return_value = canal
        conexion.is_open = True
        monkeypatch.setattr("app.messaging.publicador.pika.BlockingConnection", lambda _p: conexion)

        with app.test_request_context("/ordenes-compra"):
            from flask import g

            g.correlation_id = "corr-rmq-99"
            id_ev = publicar_orden_actualizada(
                id_orden=4,
                numero="OC-2026-000004",
                id_proveedor=2,
                estado="APROBADA",
                total=Decimal("150000.50"),
            )

        assert isinstance(id_ev, str) and len(id_ev) > 10
        canal.exchange_declare.assert_called_once_with(
            exchange="inventario.eventos",
            exchange_type="topic",
            durable=True,
        )
        canal.confirm_delivery.assert_called_once()
        kwargs = canal.basic_publish.call_args.kwargs
        assert kwargs["exchange"] == "inventario.eventos"
        assert kwargs["routing_key"] == "OrdenCompraActualizada"
        assert kwargs["properties"].delivery_mode == 2
        assert kwargs["properties"].correlation_id == "corr-rmq-99"

        cuerpo = json.loads(kwargs["body"].decode("utf-8"))
        assert cuerpo["tipo"] == "OrdenCompraActualizada"
        assert cuerpo["productor"] == "ms-compras"
        assert cuerpo["id_correlacion"] == "corr-rmq-99"
        assert cuerpo["fecha"].endswith("Z")
        assert cuerpo["datos"]["total"] == 150000.5
        conexion.close.assert_called_once()

    def test_publica_mercancia_recibida_y_devolucion_registrada(self, app, monkeypatch):
        canal = MagicMock()
        conexion = MagicMock()
        conexion.channel.return_value = canal
        conexion.is_open = True
        monkeypatch.setattr("app.messaging.publicador.pika.BlockingConnection", lambda _p: conexion)

        with app.test_request_context("/"):
            publicar_mercancia_recibida(
                id_orden=1,
                id_recepcion=10,
                id_bodega=2,
                id_usuario=7,
                items=[{"sku": "SKU-1", "cantidad": Decimal("5.000"), "costo_unitario": Decimal("120.00")}],
            )
            publicar_devolucion_registrada(
                id_orden=1,
                id_devolucion=3,
                id_bodega=2,
                id_usuario=7,
                motivo="Empaque roto",
                items=[{"sku": "SKU-1", "cantidad": Decimal("1.000")}],
            )

        rutas = [call.kwargs["routing_key"] for call in canal.basic_publish.call_args_list]
        assert rutas == ["MercanciaRecibida", "DevolucionProveedorRegistrada"]

    def test_fallo_rabbitmq_lanza_503_servicio_no_disponible(self, app, monkeypatch):
        def fallar_conexion(_params):
            raise AMQPConnectionError("broker caido")

        monkeypatch.setattr("app.messaging.publicador.pika.BlockingConnection", fallar_conexion)

        with app.test_request_context("/"):
            with pytest.raises(ErrorAPI) as exc:
                publicar_orden_actualizada(1, "OC-2026-000001", 1, "BORRADOR", Decimal("10.00"))
            assert exc.value.status_code == 503
            assert exc.value.codigo == "SERVICIO_NO_DISPONIBLE"
