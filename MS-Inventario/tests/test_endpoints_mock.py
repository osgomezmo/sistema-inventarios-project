"""Pruebas unitarias con mocking de todos los endpoints y eventos de ms-inventario.

Verifica la recepcion, validacion, manejo y retorno de cada endpoint (bodegas,
stock, movimientos, kardex, traslados, devoluciones de cliente y eventos AMQP)
sin depender de un servidor MySQL o RabbitMQ activo, cubriendo casos verdaderos,
absurdos, ilogicos y fuera de rango.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import json
import mysql.connector
import pytest

import app.routes.bodegas as rutas_bodegas
import app.routes.devoluciones as rutas_dev
import app.routes.kardex as rutas_kardex
import app.routes.movimientos as rutas_mov
import app.routes.stock as rutas_stock
import app.routes.traslados as rutas_tras
import app.servicios.eventos_entrantes as srv_eventos
import app.servicios.movimientos as srv_mov
from app import create_app
from app.errors import ApiError

TOKEN = "token-unitario-inventario"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "X-User-Id": "7", "X-Correlation-Id": "corr-inv-1"}


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "SERVICE_TOKEN": TOKEN})
    return app.test_client()


def mock_transaccion(monkeypatch, *modulos):
    """Parchea transaccion() en los modulos indicados con un cursor simulado."""
    estado = {"commits": 0, "rollbacks": 0, "ejecutadas": []}

    class _FakeCursor:
        def execute(self, sql, params=()):
            estado["ejecutadas"].append((sql, params))

    cursor = _FakeCursor()

    @contextmanager
    def _tx():
        try:
            yield cursor
            estado["commits"] += 1
        except Exception:
            estado["rollbacks"] += 1
            raise

    for mod in modulos:
        monkeypatch.setattr(mod, "transaccion", _tx)
    return estado


class TestEndpointsBodegasYStockMock:
    def test_casos_reales_bodegas_y_stock(self, client, monkeypatch):
        mock_transaccion(monkeypatch, rutas_bodegas, rutas_stock)

        bodega_base = {
            "id_bodega": 1,
            "codigo": "BOD-CENTRAL",
            "nombre": "Bodega Central",
            "direccion": "Zona Industrial Calle 10",
            "estado": "ACTIVO",
        }

        # 1. GET /bodegas
        monkeypatch.setattr(
            rutas_bodegas.repo,
            "listar",
            lambda _c, _est, _pp, _off: ([dict(bodega_base)], 1),
        )
        res_list = client.get("/bodegas?estado=ACTIVO&page=1&per_page=10", headers=HEADERS)
        assert res_list.status_code == 200
        assert res_list.get_json()["data"][0]["codigo"] == "BOD-CENTRAL"

        # 2. GET /bodegas/{id}
        monkeypatch.setattr(rutas_bodegas.repo, "obtener", lambda _c, _id: dict(bodega_base))
        assert client.get("/bodegas/1", headers=HEADERS).status_code == 200

        # 3. POST /bodegas
        monkeypatch.setattr(rutas_bodegas.repo, "insertar", lambda _c, **_kw: 1)
        res_post = client.post(
            "/bodegas",
            headers=HEADERS,
            json={"codigo": " bod-central ", "nombre": "Bodega Central", "direccion": "Calle 10"},
        )
        assert res_post.status_code == 201
        assert res_post.get_json()["codigo"] == "BOD-CENTRAL"

        # 4. PUT /bodegas/{id}, inactivar y activar
        monkeypatch.setattr(rutas_bodegas.repo, "obtener_bloqueando", lambda _c, _id: dict(bodega_base))
        monkeypatch.setattr(rutas_bodegas.repo, "actualizar", lambda *_a, **_k: None)
        monkeypatch.setattr(rutas_bodegas.repo, "actualizar_estado", lambda *_a, **_k: None)
        assert (
            client.put(
                "/bodegas/1",
                headers=HEADERS,
                json={"nombre": "Bodega Norte", "direccion": "Av 30"},
            ).status_code
            == 200
        )
        res_inact = client.post("/bodegas/1/inactivar", headers=HEADERS)
        assert res_inact.status_code == 200
        assert res_inact.get_json()["estado"] == "INACTIVO"

        bodega_inact = dict(bodega_base, estado="INACTIVO")
        monkeypatch.setattr(rutas_bodegas.repo, "obtener_bloqueando", lambda _c, _id: dict(bodega_inact))
        res_act = client.post("/bodegas/1/activar", headers=HEADERS)
        assert res_act.status_code == 200
        assert res_act.get_json()["estado"] == "ACTIVO"

        # 5. GET /stock y GET /stock/{sku}
        fila_stock = {
            "sku": "LAC-0001",
            "id_bodega": 1,
            "cantidad": Decimal("8.000"),
            "costo_promedio": Decimal("3500.0000"),
            "valor": Decimal("28000.00"),
            "stock_minimo": Decimal("10.000"),
            "bajo_minimo": 1,
            "actualizado_en": datetime(2026, 11, 16, 20, 0, 0, tzinfo=timezone.utc),
        }
        monkeypatch.setattr(
            rutas_stock.repo,
            "listar",
            lambda _c, _pp, _off, **_f: ([dict(fila_stock)], 1),
        )
        res_stock = client.get("/stock?sku=LAC-0001&id_bodega=1&bajo_minimo=true", headers=HEADERS)
        assert res_stock.status_code == 200
        assert res_stock.get_json()["data"][0]["valor"] == 28000.0

        monkeypatch.setattr(
            rutas_stock.repo,
            "saldos_de_sku",
            lambda _c, _sku: [
                {
                    "sku": "LAC-0001",
                    "id_bodega": 1,
                    "cantidad": Decimal("8.000"),
                    "costo_promedio": Decimal("3500.0000"),
                    "valor": Decimal("28000.00"),
                },
                {
                    "sku": "LAC-0001",
                    "id_bodega": 2,
                    "cantidad": Decimal("12.000"),
                    "costo_promedio": Decimal("3500.0000"),
                    "valor": Decimal("42000.00"),
                },
            ],
        )
        res_sku_stock = client.get("/stock/lac-0001", headers=HEADERS)
        assert res_sku_stock.status_code == 200
        assert res_sku_stock.get_json() == {
            "sku": "LAC-0001",
            "por_bodega": [
                {"id_bodega": 1, "cantidad": 8.0, "costo_promedio": 3500.0, "valor": 28000.0},
                {"id_bodega": 2, "cantidad": 12.0, "costo_promedio": 3500.0, "valor": 42000.0},
            ],
            "total": {"cantidad": 20.0, "valor": 70000.0},
        }

    def test_casos_ilogicos_y_fuera_de_rango_bodegas_y_stock(self, client, monkeypatch):
        mock_transaccion(monkeypatch, rutas_bodegas, rutas_stock)

        # Codigo de bodega duplicado -> 409 CODIGO_DUPLICADO
        def dup_bodega(*_a, **_k):
            raise mysql.connector.IntegrityError(msg="Duplicate", errno=1062)

        monkeypatch.setattr(rutas_bodegas.repo, "insertar", dup_bodega)
        res_dup = client.post(
            "/bodegas",
            headers=HEADERS,
            json={"codigo": "BOD-CENTRAL", "nombre": "Bodega", "direccion": "Dir"},
        )
        assert res_dup.status_code == 409
        assert res_dup.get_json()["error"]["codigo"] == "CODIGO_DUPLICADO"

        # Entradas absurdas en POST /bodegas: codigo con espacios/ñ, nombre vacio, direccion booleana
        res_bad = client.post(
            "/bodegas",
            headers=HEADERS,
            json={"codigo": "BOD CON ESPACIOS!", "nombre": "  ", "direccion": True},
        )
        assert res_bad.status_code == 422
        assert set(res_bad.get_json()["error"]["detalles"]) == {"codigo", "nombre", "direccion"}

        # Stock de SKU > 50 caracteres o sin saldos -> 404 NO_EXISTE
        monkeypatch.setattr(rutas_stock.repo, "saldos_de_sku", lambda _c, _s: [])
        assert client.get(f"/stock/{'X' * 51}", headers=HEADERS).status_code == 404
        assert client.get("/stock/SKU-SIN-SALDO", headers=HEADERS).status_code == 404

        # Filtros ilogicos en GET /stock
        res_bad_stock = client.get(
            "/stock?id_bodega=0&bajo_minimo=quizas&page=-1",
            headers=HEADERS,
        )
        assert res_bad_stock.status_code == 422
        assert set(res_bad_stock.get_json()["error"]["detalles"]) == {
            "id_bodega",
            "bajo_minimo",
            "page",
        }


class TestEndpointsMovimientosKardexTrasladosDevolucionesMock:
    def test_casos_reales_movimientos_kardex_traslados_y_devoluciones_cliente(self, client, monkeypatch):
        mock_transaccion(monkeypatch, rutas_mov, rutas_kardex, rutas_tras, rutas_dev)
        fecha_dt = datetime(2026, 11, 16, 21, 0, 0, tzinfo=timezone.utc)

        producto_falso = {
            "sku": "LAC-0001",
            "nombre": "Leche 1 L",
            "estado": "ACTIVO",
            "unidad_medida": "UNIDAD",
            "stock_minimo": Decimal("10.000"),
            "id_categoria": 1,
        }
        monkeypatch.setattr(rutas_mov, "consultar_producto", lambda *_a, **_k: dict(producto_falso))
        monkeypatch.setattr(rutas_tras, "consultar_producto", lambda *_a, **_k: dict(producto_falso))
        monkeypatch.setattr(rutas_dev, "consultar_producto", lambda *_a, **_k: dict(producto_falso))

        eventos_publicados = []
        monkeypatch.setattr(
            rutas_mov.eventos,
            "publicar_movimiento",
            lambda res, corr=None: eventos_publicados.append((res["movimiento"]["tipo"], corr)),
        )

        # Mock de repositorios usados por aplicar_movimiento
        monkeypatch.setattr(
            srv_mov.repo_saldos,
            "leer_bodega_compartida",
            lambda _c, id_b: {"id_bodega": id_b, "estado": "ACTIVO"},
        )
        monkeypatch.setattr(srv_mov.repo_saldos, "asegurar_saldo", lambda *_a, **_k: None)
        monkeypatch.setattr(
            srv_mov.repo_saldos,
            "bloquear_saldo",
            lambda _c, _sku, id_b: {
                "id_saldo": id_b,
                "cantidad": Decimal("12.000"),
                "costo_promedio": Decimal("3000.0000"),
            },
        )
        monkeypatch.setattr(srv_mov.repo_saldos, "actualizar_saldo", lambda *_a, **_k: None)
        monkeypatch.setattr(
            srv_mov.repo_movimientos,
            "insertar_movimiento",
            lambda _c, **_kw: (101, fecha_dt),
        )
        monkeypatch.setattr(
            rutas_mov.repo,
            "obtener",
            lambda _c, id_m: {
                "id_movimiento": id_m,
                "sku": "LAC-0001",
                "id_bodega": 1,
                "tipo": "SALIDA",
                "cantidad": Decimal("4.000"),
                "costo_unitario": Decimal("3000.0000"),
                "saldo_resultante": Decimal("8.000"),
                "costo_promedio": Decimal("3000.0000"),
                "valor_resultante": Decimal("24000.00"),
                "motivo": "Venta POS",
                "documento_referencia": "POS-001",
                "id_usuario": 7,
                "fecha": fecha_dt,
            },
        )

        # 1. POST /movimientos (SALIDA que cruza stock_minimo 12 -> 8 <= 10)
        res_mov = client.post(
            "/movimientos",
            headers=HEADERS,
            json={
                "sku": "lac-0001",
                "id_bodega": 1,
                "tipo": "SALIDA",
                "cantidad": 4,
                "motivo": "Venta POS",
                "documento_referencia": "POS-001",
            },
        )
        assert res_mov.status_code == 201
        assert res_mov.get_json()["saldo_resultante"] == 8.0
        assert eventos_publicados == [("SALIDA", "corr-inv-1")]

        # 2. GET /movimientos y GET /movimientos/{id}
        monkeypatch.setattr(
            rutas_mov.repo,
            "listar",
            lambda _c, _pp, _off, **_f: ([res_mov.get_json()], 1),
        )
        assert (
            client.get(
                "/movimientos?sku=LAC-0001&id_bodega=1&tipo=SALIDA&desde=2026-11-01&hasta=2026-11-16",
                headers=HEADERS,
            ).status_code
            == 200
        )
        assert client.get("/movimientos/101", headers=HEADERS).status_code == 200

        # 3. GET /kardex
        monkeypatch.setattr(
            rutas_kardex.repo,
            "saldo_anterior",
            lambda *_a: {"saldo_resultante": Decimal("12.000"), "valor_resultante": Decimal("36000.00")},
        )
        monkeypatch.setattr(
            rutas_kardex.repo,
            "movimientos_en_rango",
            lambda *_a: [
                {
                    "id_movimiento": 101,
                    "tipo": "SALIDA",
                    "cantidad": Decimal("4.000"),
                    "saldo_resultante": Decimal("8.000"),
                    "valor_resultante": Decimal("24000.00"),
                }
            ],
        )
        res_kardex = client.get(
            "/kardex?sku=LAC-0001&id_bodega=1&desde=2026-11-01&hasta=2026-11-16",
            headers=HEADERS,
        )
        assert res_kardex.status_code == 200
        body_kardex = res_kardex.get_json()
        assert body_kardex["saldo_inicial"] == {"cantidad": 12.0, "valor": 36000.0}
        assert body_kardex["saldo_final"] == {"cantidad": 8.0, "valor": 24000.0}

        # 4. POST /traslados, GET /traslados, GET /traslados/{id}
        monkeypatch.setattr(rutas_tras.repo, "insertar", lambda *_a, **_k: 55)
        monkeypatch.setattr(
            rutas_tras.repo,
            "obtener",
            lambda _c, id_t: {
                "id_traslado": id_t,
                "sku": "LAC-0001",
                "id_bodega_origen": 1,
                "id_bodega_destino": 2,
                "cantidad": Decimal("3.000"),
                "motivo": "Reabastecimiento",
                "id_usuario": 7,
                "fecha": fecha_dt,
                "movimientos": {"salida": 102, "entrada": 103},
            },
        )
        res_tras = client.post(
            "/traslados",
            headers=HEADERS,
            json={
                "sku": "LAC-0001",
                "id_bodega_origen": 1,
                "id_bodega_destino": 2,
                "cantidad": 3,
                "motivo": "Reabastecimiento",
            },
        )
        assert res_tras.status_code == 201
        assert res_tras.get_json()["movimientos"] == {"salida": 102, "entrada": 103}

        monkeypatch.setattr(
            rutas_tras.repo,
            "listar",
            lambda _c, _pp, _off, **_f: ([res_tras.get_json()], 1),
        )
        assert client.get("/traslados?sku=LAC-0001", headers=HEADERS).status_code == 200
        assert client.get("/traslados/55", headers=HEADERS).status_code == 200

        # 5. POST /devoluciones-cliente y GET /devoluciones-cliente
        res_dev = client.post(
            "/devoluciones-cliente",
            headers=HEADERS,
            json={
                "sku": "LAC-0001",
                "id_bodega": 1,
                "cantidad": 2,
                "factura_pos": "FAC-POS-9988",
                "motivo": "Empaque sellado devuelto por cliente",
            },
        )
        assert res_dev.status_code == 201
        assert client.get("/devoluciones-cliente?sku=LAC-0001", headers=HEADERS).status_code == 200

    def test_casos_ilogicos_absurdos_y_fuera_de_rango_movimientos_kardex_y_traslados(
        self, client, monkeypatch
    ):
        mock_transaccion(monkeypatch, rutas_mov, rutas_kardex, rutas_tras, rutas_dev)

        producto_unidad = {
            "sku": "LAC-0001",
            "nombre": "Leche 1 L",
            "estado": "ACTIVO",
            "unidad_medida": "UNIDAD",
            "stock_minimo": Decimal("10.000"),
            "id_categoria": 1,
        }
        monkeypatch.setattr(rutas_mov, "consultar_producto", lambda *_a, **_k: dict(producto_unidad))
        monkeypatch.setattr(rutas_tras, "consultar_producto", lambda *_a, **_k: dict(producto_unidad))

        # 1. X-User-Id ausente, cero, negativo, decimal o > MAX_ID -> 400 PETICION_INVALIDA
        for bad_uid in ("", "0", "-5", "1.5", "abc", "2147483648"):
            res_uid = client.post(
                "/movimientos",
                headers={"Authorization": f"Bearer {TOKEN}", "X-User-Id": bad_uid},
                json={"sku": "LAC-0001", "id_bodega": 1, "tipo": "SALIDA", "cantidad": 1},
            )
            assert res_uid.status_code == 400
            assert res_uid.get_json()["error"]["codigo"] == "PETICION_INVALIDA"

        # 2. Intento de registrar ENTRADA_COMPRA por HTTP o cantidad 0 / booleana -> 422 VALIDACION
        res_tipo_prohibido = client.post(
            "/movimientos",
            headers=HEADERS,
            json={
                "sku": "LAC-0001",
                "id_bodega": True,
                "tipo": "ENTRADA_COMPRA",
                "cantidad": 0,
                "costo_unitario": -10,
            },
        )
        assert res_tipo_prohibido.status_code == 422
        assert set(res_tipo_prohibido.get_json()["error"]["detalles"]) == {
            "id_bodega",
            "tipo",
            "cantidad",
            "costo_unitario",
        }

        # 3. Ajuste sin motivo o AJUSTE_POSITIVO con saldo 0 sin costo_unitario -> 422 VALIDACION
        monkeypatch.setattr(
            srv_mov.repo_saldos,
            "leer_bodega_compartida",
            lambda _c, id_b: {"id_bodega": id_b, "estado": "ACTIVO"},
        )
        monkeypatch.setattr(srv_mov.repo_saldos, "asegurar_saldo", lambda *_a, **_k: None)
        monkeypatch.setattr(
            srv_mov.repo_saldos,
            "bloquear_saldo",
            lambda _c, _sku, id_b: {
                "id_saldo": id_b,
                "cantidad": Decimal("0.000"),
                "costo_promedio": Decimal("0.0000"),
            },
        )
        res_sin_motivo = client.post(
            "/movimientos",
            headers=HEADERS,
            json={"sku": "LAC-0001", "id_bodega": 1, "tipo": "AJUSTE_POSITIVO", "cantidad": 5},
        )
        assert res_sin_motivo.status_code == 422
        assert "motivo" in res_sin_motivo.get_json()["error"]["detalles"]

        res_sin_costo = client.post(
            "/movimientos",
            headers=HEADERS,
            json={
                "sku": "LAC-0001",
                "id_bodega": 1,
                "tipo": "AJUSTE_POSITIVO",
                "cantidad": 5,
                "motivo": "Inventario inicial sin costo",
            },
        )
        assert res_sin_costo.status_code == 422
        assert "costo_unitario" in res_sin_costo.get_json()["error"]["detalles"]

        # 4. Salida que deja saldo negativo -> 409 STOCK_INSUFICIENTE
        res_sin_stock = client.post(
            "/movimientos",
            headers=HEADERS,
            json={"sku": "LAC-0001", "id_bodega": 1, "tipo": "SALIDA", "cantidad": 1},
        )
        assert res_sin_stock.status_code == 409
        assert res_sin_stock.get_json()["error"]["codigo"] == "STOCK_INSUFICIENTE"

        # 5. Traslado ilogico: misma bodega origen y destino -> 422 VALIDACION
        res_misma_bod = client.post(
            "/traslados",
            headers=HEADERS,
            json={"sku": "LAC-0001", "id_bodega_origen": 2, "id_bodega_destino": 2, "cantidad": 3},
        )
        assert res_misma_bod.status_code == 422
        assert "id_bodega_destino" in res_misma_bod.get_json()["error"]["detalles"]

        # 6. Kardex sin parametros obligatorios o con desde > hasta -> 422 VALIDACION
        res_kardex_incompleto = client.get("/kardex?sku=LAC-0001", headers=HEADERS)
        assert res_kardex_incompleto.status_code == 422
        assert set(res_kardex_incompleto.get_json()["error"]["detalles"]) == {
            "id_bodega",
            "desde",
            "hasta",
        }

        res_kardex_invertido = client.get(
            "/kardex?sku=LAC-0001&id_bodega=1&desde=2026-11-20&hasta=2026-11-01",
            headers=HEADERS,
        )
        assert res_kardex_invertido.status_code == 422
        assert "desde" in res_kardex_invertido.get_json()["error"]["detalles"]

        # 7. Fallo de ms-productos -> 503 SERVICIO_NO_DISPONIBLE
        def prod_caido(*_a, **_k):
            raise ApiError("SERVICIO_NO_DISPONIBLE", "El servicio de productos no responde.", 503)

        monkeypatch.setattr(rutas_mov, "consultar_producto", prod_caido)
        res_503 = client.post(
            "/movimientos",
            headers=HEADERS,
            json={"sku": "LAC-0001", "id_bodega": 1, "tipo": "SALIDA", "cantidad": 1},
        )
        assert res_503.status_code == 503
        assert res_503.get_json()["error"]["codigo"] == "SERVICIO_NO_DISPONIBLE"


class TestEventosEntrantesRabbitMQMock:
    def test_procesa_mercancia_recibida_idempotencia_y_rechaza_eventos_absurdos(self, monkeypatch):
        mock_transaccion(monkeypatch, srv_eventos)
        monkeypatch.setattr(
            srv_eventos,
            "consultar_producto",
            lambda sku, _corr=None: {
                "sku": sku.upper(),
                "nombre": "Leche 1 L",
                "estado": "ACTIVO",
                "unidad_medida": "UNIDAD",
                "stock_minimo": Decimal("5.000"),
                "id_categoria": 1,
            },
        )
        aplicados = []
        monkeypatch.setattr(
            srv_eventos,
            "aplicar_movimiento",
            lambda _c, **kw: aplicados.append(kw) or {"movimiento": kw, "cruzo_umbral": False},
        )

        cuerpo_valido = json.dumps(
            {
                "id_evento": "6f1c2a9e-1b7d-4c55-9a51-3f0e8d2b7c10",
                "tipo": "MercanciaRecibida",
                "fecha": "2026-11-16T20:00:00Z",
                "productor": "ms-compras",
                "id_correlacion": "c1f4b8e2-77a0-4d1e-9a3b-0c5d6e7f8a90",
                "datos": {
                    "id_orden": 15,
                    "id_recepcion": 31,
                    "id_bodega": 2,
                    "id_usuario": 7,
                    "items": [{"sku": "lac-0001", "cantidad": 24, "costo_unitario": 3150.25}],
                },
            }
        )
        proc = srv_eventos.procesar_evento(cuerpo_valido)
        assert proc.ya_procesado is False
        assert len(proc.resultados) == 1
        assert aplicados[0]["tipo"] == "ENTRADA_COMPRA"
        assert aplicados[0]["documento_referencia"] == "OC-15"

        # Evento duplicado (errno 1062 en eventos_procesados) -> ya_procesado=True sin reaplicar
        @contextmanager
        def _tx_duplicada():
            class _CurDup:
                def execute(self, *_a):
                    raise mysql.connector.IntegrityError(msg="Duplicate", errno=1062)

            yield _CurDup()

        monkeypatch.setattr(srv_eventos, "transaccion", _tx_duplicada)
        proc_dup = srv_eventos.procesar_evento(cuerpo_valido)
        assert proc_dup.ya_procesado is True
        assert proc_dup.resultados == []

        # Eventos absurdos / corruptos -> EventoInvalido
        for invalido in (
            "no es json",
            json.dumps(["lista"]),
            json.dumps({"id_evento": "no-uuid", "tipo": "MercanciaRecibida", "datos": {}}),
            json.dumps(
                {
                    "id_evento": "6f1c2a9e-1b7d-4c55-9a51-3f0e8d2b7c10",
                    "tipo": "EventoInventado",
                    "datos": {},
                }
            ),
            json.dumps(
                {
                    "id_evento": "6f1c2a9e-1b7d-4c55-9a51-3f0e8d2b7c10",
                    "tipo": "MercanciaRecibida",
                    "datos": {
                        "id_orden": True,
                        "id_recepcion": 1,
                        "id_bodega": 1,
                        "id_usuario": 1,
                        "items": [],
                    },
                }
            ),
        ):
            with pytest.raises(srv_eventos.EventoInvalido):
                srv_eventos.leer_evento(invalido)
