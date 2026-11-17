"""Pruebas unitarias de rutas HTTP, RBAC, maquina de estados y rollback."""

from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from app.errors import ErrorAPI
from tests.conftest import auth_headers


class FakeCursor:
    """Cursor FIFO programable para aislar logica SQL en pruebas unitarias."""

    def __init__(self, respuestas=None):
        self._respuestas = list(respuestas or [])
        self.lastrowid = 1
        self.ejecutadas = []

    def execute(self, sql, params=()):
        self.ejecutadas.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self._respuestas.pop(0) if self._respuestas else None

    def fetchall(self):
        return self._respuestas.pop(0) if self._respuestas else []

    def close(self):
        pass


class FakeConexion:
    """Conexion falsa que registra start_transaction, commit y rollback."""

    def __init__(self):
        self.iniciada = 0
        self.commits = 0
        self.rollbacks = 0

    def start_transaction(self):
        self.iniciada += 1

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


def parchar_transaccion(monkeypatch, modulo, cursor):
    """Inyecta una transaccion falsa preservando el manejo exacto de rollback/commit."""
    conexion = FakeConexion()

    @contextmanager
    def fake_tx():
        try:
            conexion.start_transaction()
            yield conexion, cursor
            conexion.commit()
        except Exception:
            conexion.rollback()
            raise

    monkeypatch.setattr(modulo, "transaccion", fake_tx)
    return conexion


def parchar_lectura(monkeypatch, modulo, cursor):
    conexion = FakeConexion()

    @contextmanager
    def fake_conn():
        yield conexion, cursor

    monkeypatch.setattr(modulo, "obtener_conexion", fake_conn)
    return conexion


class TestSaludYSeguridadHTTP:
    def test_health_y_health_ready(self, client, monkeypatch):
        res_live = client.get("/health")
        assert res_live.status_code == 200
        assert res_live.get_json() == {"status": "ok", "service": "ms-compras"}

        monkeypatch.setattr("app.routes.health.verificar_salud_db", lambda: None)
        monkeypatch.setattr("app.routes.health.verificar_salud_rabbitmq", lambda: None)
        res_ready = client.get("/health/ready")
        assert res_ready.status_code == 200
        assert res_ready.get_json()["dependencias"] == {"mysql": "ok", "rabbitmq": "ok"}

        def rmx_caido():
            raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "RabbitMQ no disponible.")

        monkeypatch.setattr("app.routes.health.verificar_salud_rabbitmq", rmx_caido)
        res_fail = client.get("/health/ready")
        assert res_fail.status_code == 503
        assert res_fail.get_json()["error"]["codigo"] == "SERVICIO_NO_DISPONIBLE"

    def test_autenticacion_y_control_de_roles_rbac(self, client):
        assert client.get("/ordenes-compra").status_code == 401
        assert (
            client.get(
                "/ordenes-compra",
                headers={"Authorization": "Bearer invalido", "X-User-Id": "1", "X-User-Role": "admin"},
            ).status_code
            == 401
        )
        assert (
            client.get(
                "/ordenes-compra",
                headers={"Authorization": "Bearer token-secreto-pruebas-compras", "X-User-Id": "0", "X-User-Role": "admin"},
            ).status_code
            == 401
        )

        # jefe_bodega no puede crear ordenes; compras no puede aprobar ni anular; gerente no puede recibir
        payload_orden = {
            "id_proveedor": 1,
            "id_bodega_destino": 1,
            "items": [{"sku": "SKU-1", "cantidad": 2, "precio_unitario": 100}],
        }
        assert (
            client.post("/ordenes-compra", json=payload_orden, headers=auth_headers("jefe_bodega")).status_code
            == 403
        )
        assert client.post("/ordenes-compra/1/aprobar", headers=auth_headers("compras")).status_code == 403
        assert (
            client.post("/ordenes-compra/1/anular", json={"motivo": "test"}, headers=auth_headers("compras")).status_code
            == 403
        )
        assert (
            client.post(
                "/ordenes-compra/1/recepciones",
                json={"items": [{"id_detalle": 1, "cantidad": 1}]},
                headers=auth_headers("gerente"),
            ).status_code
            == 403
        )


class TestFlujoOrdenesRecepcionesDevoluciones:
    def test_crea_orden_valida_y_ejecuta_rollback_si_rabbitmq_falla(self, client, monkeypatch):
        import app.repositorios.ordenes as repo_ordenes

        monkeypatch.setattr(repo_ordenes, "validar_proveedor_activo", lambda _id: {"id_proveedor": 2, "estado": "ACTIVO"})

        ahora = datetime(2026, 11, 14, 17, 0, 0)
        cursor_ok = FakeCursor(
            [
                {
                    "id_orden": 1,
                    "numero": "OC-2026-000001",
                    "id_proveedor": 2,
                    "id_bodega_destino": 1,
                    "estado": "BORRADOR",
                    "total": Decimal("250.00"),
                    "id_usuario_creador": 7,
                    "id_usuario_aprobador": None,
                    "motivo_anulacion": None,
                    "creada_en": ahora,
                    "aprobada_en": None,
                    "actualizada_en": ahora,
                },
                [{"id_detalle": 10, "id_orden": 1, "sku": "SKU-A", "cantidad_pedida": Decimal("2.500"), "cantidad_recibida": Decimal("0.000"), "cantidad_devuelta": Decimal("0.000"), "precio_unitario": Decimal("100.00")}],
                [],
                [],
            ]
        )
        tx_ok = parchar_transaccion(monkeypatch, repo_ordenes, cursor_ok)
        publicado = {}

        def fake_pub(**kwargs):
            publicado.update(kwargs)
            return "ev-1"

        monkeypatch.setattr(repo_ordenes, "publicar_orden_actualizada", fake_pub)

        res = client.post(
            "/ordenes-compra",
            json={
                "id_proveedor": 2,
                "id_bodega_destino": 1,
                "items": [{"sku": "sku-a", "cantidad": "2.5", "precio_unitario": 100}],
            },
            headers=auth_headers("compras"),
        )
        assert res.status_code == 201
        assert tx_ok.commits == 1
        assert tx_ok.rollbacks == 0
        assert res.get_json()["numero"] == "OC-2026-000001"
        assert publicado["total"] == Decimal("250.00")

        # Simulacion de RabbitMQ caido -> rollback obligatorio sin commit
        cursor_fail = FakeCursor()
        tx_fail = parchar_transaccion(monkeypatch, repo_ordenes, cursor_fail)

        def fail_pub(**_kwargs):
            raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "RabbitMQ no disponible.")

        monkeypatch.setattr(repo_ordenes, "publicar_orden_actualizada", fail_pub)
        res_fail = client.post(
            "/ordenes-compra",
            json={
                "id_proveedor": 2,
                "id_bodega_destino": 1,
                "items": [{"sku": "sku-a", "cantidad": 2, "precio_unitario": 100}],
            },
            headers=auth_headers("compras"),
        )
        assert res_fail.status_code == 503
        assert res_fail.get_json()["error"]["codigo"] == "SERVICIO_NO_DISPONIBLE"
        assert tx_fail.rollbacks == 1
        assert tx_fail.commits == 0

    def test_bloquea_transiciones_ilogicas_en_put_aprobar_y_anular(self, client, monkeypatch):
        import app.repositorios.ordenes as repo_ordenes

        # PUT sobre orden APROBADA -> 409 ESTADO_NO_EDITABLE
        cursor_put = FakeCursor([{"id_orden": 5, "estado": "APROBADA"}])
        parchar_lectura(monkeypatch, repo_ordenes, cursor_put)
        res_put = client.put(
            "/ordenes-compra/5",
            json={
                "id_proveedor": 1,
                "id_bodega_destino": 1,
                "items": [{"sku": "SKU-1", "cantidad": 1, "precio_unitario": 50}],
            },
            headers=auth_headers("compras"),
        )
        assert res_put.status_code == 409
        assert res_put.get_json()["error"]["codigo"] == "ESTADO_NO_EDITABLE"

        # Aprobar orden ya ANULADA -> 409 TRANSICION_INVALIDA
        cursor_aprob = FakeCursor([{"id_orden": 5, "estado": "ANULADA"}])
        tx_aprob = parchar_transaccion(monkeypatch, repo_ordenes, cursor_aprob)
        res_aprob = client.post("/ordenes-compra/5/aprobar", headers=auth_headers("gerente"))
        assert res_aprob.status_code == 409
        assert res_aprob.get_json()["error"]["codigo"] == "TRANSICION_INVALIDA"
        assert tx_aprob.rollbacks == 1

        # Anular orden APROBADA que ya tiene recepciones -> 409 TRANSICION_INVALIDA
        cursor_anul = FakeCursor([{"id_orden": 5, "estado": "APROBADA"}, {"cnt": 1}])
        tx_anul = parchar_transaccion(monkeypatch, repo_ordenes, cursor_anul)
        res_anul = client.post(
            "/ordenes-compra/5/anular",
            json={"motivo": "Intento ilogico tras recibir mercancia"},
            headers=auth_headers("admin"),
        )
        assert res_anul.status_code == 409
        assert res_anul.get_json()["error"]["codigo"] == "TRANSICION_INVALIDA"
        assert tx_anul.rollbacks == 1

    def test_recepcion_parcial_total_y_cantidad_mayor_que_pendiente(self, client, monkeypatch):
        import app.repositorios.recepciones as repo_rec

        orden_aprobada = {
            "id_orden": 8,
            "numero": "OC-2026-000008",
            "id_proveedor": 2,
            "id_bodega_destino": 3,
            "estado": "APROBADA",
            "total": Decimal("1000.00"),
        }
        detalle_orden = [
            {
                "id_detalle": 21,
                "id_orden": 8,
                "sku": "HARINA-1KG",
                "cantidad_pedida": Decimal("10.000"),
                "cantidad_recibida": Decimal("4.000"),
                "cantidad_devuelta": Decimal("0.000"),
                "precio_unitario": Decimal("100.00"),
            }
        ]

        # Exceso: pide recibir 7 cuando solo faltan 6 -> 409 CANTIDAD_MAYOR_QUE_PENDIENTE
        cursor_exc = FakeCursor([dict(orden_aprobada), [dict(detalle_orden[0])]])
        tx_exc = parchar_transaccion(monkeypatch, repo_rec, cursor_exc)
        res_exc = client.post(
            "/ordenes-compra/8/recepciones",
            json={"items": [{"id_detalle": 21, "cantidad": 7}]},
            headers=auth_headers("jefe_bodega"),
        )
        assert res_exc.status_code == 409
        assert res_exc.get_json()["error"]["codigo"] == "CANTIDAD_MAYOR_QUE_PENDIENTE"
        assert tx_exc.rollbacks == 1

        # Recepcion exacta del saldo restante (6) -> transiciona a RECIBIDA
        ahora = datetime(2026, 11, 14, 18, 0, 0)
        cursor_ok = FakeCursor(
            [
                dict(orden_aprobada),
                [dict(detalle_orden[0])],
                {
                    "id_recepcion": 1,
                    "id_orden": 8,
                    "fecha": ahora,
                    "id_usuario": 7,
                    "observaciones": "Saldo final",
                },
            ]
        )
        tx_ok = parchar_transaccion(monkeypatch, repo_rec, cursor_ok)
        eventos = []
        monkeypatch.setattr(repo_rec, "publicar_mercancia_recibida", lambda **kw: eventos.append(("MercanciaRecibida", kw)))
        monkeypatch.setattr(repo_rec, "publicar_orden_actualizada", lambda **kw: eventos.append(("OrdenCompraActualizada", kw)))

        res_ok = client.post(
            "/ordenes-compra/8/recepciones",
            json={"observaciones": "Saldo final", "items": [{"id_detalle": 21, "cantidad": 6}]},
            headers=auth_headers("jefe_bodega"),
        )
        assert res_ok.status_code == 201
        assert tx_ok.commits == 1
        assert res_ok.get_json()["estado_orden"] == "RECIBIDA"
        assert [ev[0] for ev in eventos] == ["MercanciaRecibida", "OrdenCompraActualizada"]
        assert eventos[1][1]["estado"] == "RECIBIDA"

    def test_devolucion_valida_y_rechazo_sobre_recibido_disponible(self, client, monkeypatch):
        import app.repositorios.devoluciones as repo_dev

        orden_recibida = {
            "id_orden": 8,
            "numero": "OC-2026-000008",
            "id_proveedor": 2,
            "id_bodega_destino": 3,
            "estado": "RECIBIDA_PARCIAL",
            "total": Decimal("1000.00"),
        }
        detalle = {
            "id_detalle": 21,
            "id_orden": 8,
            "sku": "HARINA-1KG",
            "cantidad_pedida": Decimal("10.000"),
            "cantidad_recibida": Decimal("5.000"),
            "cantidad_devuelta": Decimal("2.000"),
            "precio_unitario": Decimal("100.00"),
        }

        # Disponible = 5 - 2 = 3; intenta devolver 4 -> 409 CANTIDAD_MAYOR_QUE_RECIBIDA
        cursor_exc = FakeCursor([dict(orden_recibida), [dict(detalle)]])
        tx_exc = parchar_transaccion(monkeypatch, repo_dev, cursor_exc)
        res_exc = client.post(
            "/ordenes-compra/8/devoluciones",
            json={"motivo": "Exceso devolucion", "items": [{"id_detalle": 21, "cantidad": 4}]},
            headers=auth_headers("compras"),
        )
        assert res_exc.status_code == 409
        assert res_exc.get_json()["error"]["codigo"] == "CANTIDAD_MAYOR_QUE_RECIBIDA"
        assert tx_exc.rollbacks == 1

        # Orden en BORRADOR no acepta devoluciones -> 409 TRANSICION_INVALIDA
        cursor_borrador = FakeCursor([{"id_orden": 9, "estado": "BORRADOR"}])
        parchar_transaccion(monkeypatch, repo_dev, cursor_borrador)
        res_borr = client.post(
            "/ordenes-compra/9/devoluciones",
            json={"motivo": "Sin recibir", "items": [{"id_detalle": 1, "cantidad": 1}]},
            headers=auth_headers("compras"),
        )
        assert res_borr.status_code == 409
        assert res_borr.get_json()["error"]["codigo"] == "TRANSICION_INVALIDA"

    def test_filtros_de_consulta_ordenes_y_devoluciones(self, client, monkeypatch):
        import app.repositorios.ordenes as repo_ordenes
        import app.routes.ordenes as rutas_ordenes
        import app.routes.devoluciones as rutas_devoluciones

        res_estado_malo = client.get(
            "/ordenes-compra?estado=INEXISTENTE",
            headers=auth_headers("admin"),
        )
        assert res_estado_malo.status_code == 422

        res_rango_ilogico = client.get(
            "/devoluciones-proveedor?desde=2026-11-20&hasta=2026-11-01",
            headers=auth_headers("compras"),
        )
        assert res_rango_ilogico.status_code == 422

        monkeypatch.setattr(rutas_ordenes, "listar_ordenes", lambda **_kw: ([{"id_orden": 1}], 1))
        res_ord = client.get(
            "/ordenes-compra?estado=APROBADA&id_proveedor=2&page=1&per_page=10",
            headers=auth_headers("jefe_bodega"),
        )
        assert res_ord.status_code == 200
        assert res_ord.get_json()["meta"]["total"] == 1

        monkeypatch.setattr(rutas_devoluciones, "listar_devoluciones", lambda **_kw: ([{"id_devolucion": 3}], 1))
        res_dev = client.get(
            "/devoluciones-proveedor?id_proveedor=2&page=1&per_page=20",
            headers=auth_headers("compras"),
        )
        assert res_dev.status_code == 200
        assert res_dev.get_json()["data"] == [{"id_devolucion": 3}]

        ahora = datetime(2026, 11, 14, 19, 0, 0)
        cursor_detalle = FakeCursor(
            [
                {
                    "id_orden": 15,
                    "numero": "OC-2026-000015",
                    "id_proveedor": 2,
                    "id_bodega_destino": 1,
                    "estado": "RECIBIDA_PARCIAL",
                    "total": Decimal("1000.00"),
                    "id_usuario_creador": 4,
                    "id_usuario_aprobador": 2,
                    "motivo_anulacion": None,
                    "creada_en": ahora,
                    "aprobada_en": ahora,
                    "actualizada_en": ahora,
                },
                [
                    {
                        "id_detalle": 21,
                        "id_orden": 15,
                        "sku": "LAC-0001",
                        "cantidad_pedida": Decimal("10.000"),
                        "cantidad_recibida": Decimal("6.000"),
                        "cantidad_devuelta": Decimal("1.000"),
                        "precio_unitario": Decimal("100.00"),
                    }
                ],
                [
                    {
                        "id_recepcion": 31,
                        "id_orden": 15,
                        "fecha": ahora,
                        "id_usuario": 7,
                        "observaciones": "Entrega parcial",
                    }
                ],
                [
                    {
                        "id_recepcion": 31,
                        "id_detalle": 21,
                        "sku": "LAC-0001",
                        "cantidad": Decimal("6.000"),
                        "precio_unitario": Decimal("100.00"),
                    }
                ],
                [
                    {
                        "id_devolucion": 41,
                        "id_orden": 15,
                        "fecha": ahora,
                        "motivo": "Empaque roto",
                        "id_usuario": 7,
                    }
                ],
                [
                    {
                        "id_devolucion": 41,
                        "id_detalle": 21,
                        "sku": "LAC-0001",
                        "cantidad": Decimal("1.000"),
                    }
                ],
            ]
        )
        parchar_lectura(monkeypatch, repo_ordenes, cursor_detalle)
        res_det = client.get("/ordenes-compra/15", headers=auth_headers("jefe_bodega"))
        assert res_det.status_code == 200
        cuerpo_det = res_det.get_json()
        assert cuerpo_det["recepciones"][0]["items"] == [
            {"id_detalle": 21, "sku": "LAC-0001", "cantidad": 6.0, "precio_unitario": 100.0}
        ]
        assert cuerpo_det["devoluciones"][0]["items"] == [
            {"id_detalle": 21, "sku": "LAC-0001", "cantidad": 1.0}
        ]

    def test_flujo_completo_put_aprobar_anular_listar_recepciones_y_crear_devolucion(
        self, client, monkeypatch
    ):
        import app.repositorios.ordenes as repo_ordenes
        import app.repositorios.recepciones as repo_rec
        import app.repositorios.devoluciones as repo_dev

        ahora = datetime(2026, 11, 15, 10, 0, 0)
        monkeypatch.setattr(
            repo_ordenes,
            "validar_proveedor_activo",
            lambda _id: {"id_proveedor": 2, "estado": "ACTIVO"},
        )
        eventos_orden = []
        monkeypatch.setattr(
            repo_ordenes,
            "publicar_orden_actualizada",
            lambda **kw: eventos_orden.append(kw) or "ev-ord",
        )

        # 1. PUT /ordenes-compra/12 en estado BORRADOR -> 200
        orden_borrador = {
            "id_orden": 12,
            "numero": "OC-2026-000012",
            "id_proveedor": 2,
            "id_bodega_destino": 1,
            "estado": "BORRADOR",
            "total": Decimal("600.00"),
            "id_usuario_creador": 7,
            "id_usuario_aprobador": None,
            "motivo_anulacion": None,
            "creada_en": ahora,
            "aprobada_en": None,
            "actualizada_en": ahora,
        }
        cursor_put_read = FakeCursor([dict(orden_borrador)])
        parchar_lectura(monkeypatch, repo_ordenes, cursor_put_read)
        cursor_put_tx = FakeCursor(
            [
                dict(orden_borrador),
                dict(orden_borrador, total=Decimal("900.00")),
                [
                    {
                        "id_detalle": 30,
                        "id_orden": 12,
                        "sku": "ACEITE-1L",
                        "cantidad_pedida": Decimal("3.000"),
                        "cantidad_recibida": Decimal("0.000"),
                        "cantidad_devuelta": Decimal("0.000"),
                        "precio_unitario": Decimal("300.00"),
                    }
                ],
                [],
                [],
            ]
        )
        parchar_transaccion(monkeypatch, repo_ordenes, cursor_put_tx)
        res_put = client.put(
            "/ordenes-compra/12",
            json={
                "id_proveedor": 2,
                "id_bodega_destino": 1,
                "items": [{"sku": "aceite-1l", "cantidad": 3, "precio_unitario": 300}],
            },
            headers=auth_headers("compras"),
        )
        assert res_put.status_code == 200
        assert res_put.get_json()["total"] == 900.0

        # 2. POST /ordenes-compra/12/aprobar -> 200 APROBADA
        cursor_aprob = FakeCursor(
            [
                dict(orden_borrador),
                dict(orden_borrador, estado="APROBADA", id_usuario_aprobador=9, aprobada_en=ahora),
                [],
                [],
                [],
            ]
        )
        parchar_transaccion(monkeypatch, repo_ordenes, cursor_aprob)
        res_aprob = client.post("/ordenes-compra/12/aprobar", headers=auth_headers("gerente", user_id=9))
        assert res_aprob.status_code == 200
        assert res_aprob.get_json()["estado"] == "APROBADA"

        # 3. POST /ordenes-compra/12/anular (sin recepciones) -> 200 ANULADA
        cursor_anul = FakeCursor(
            [
                dict(orden_borrador, estado="APROBADA"),
                {"cnt": 0},
                dict(orden_borrador, estado="ANULADA", motivo_anulacion="Error en pedido"),
                [],
                [],
                [],
            ]
        )
        parchar_transaccion(monkeypatch, repo_ordenes, cursor_anul)
        res_anul = client.post(
            "/ordenes-compra/12/anular",
            json={"motivo": "Error en pedido"},
            headers=auth_headers("gerente"),
        )
        assert res_anul.status_code == 200
        assert res_anul.get_json()["estado"] == "ANULADA"

        # 4. GET /ordenes-compra/12/recepciones -> 200 lista con items
        cursor_list_rec = FakeCursor(
            [
                dict(orden_borrador, estado="RECIBIDA"),
                [
                    {
                        "id_recepcion": 5,
                        "id_orden": 12,
                        "fecha": ahora,
                        "id_usuario": 7,
                        "observaciones": "Completa",
                    }
                ],
                [
                    {
                        "id_recepcion": 5,
                        "id_detalle": 30,
                        "sku": "ACEITE-1L",
                        "cantidad": Decimal("3.000"),
                        "precio_unitario": Decimal("300.00"),
                    }
                ],
            ]
        )
        parchar_lectura(monkeypatch, repo_rec, cursor_list_rec)
        res_list_rec = client.get("/ordenes-compra/12/recepciones", headers=auth_headers("jefe_bodega"))
        assert res_list_rec.status_code == 200
        assert res_list_rec.get_json()[0]["items"][0]["sku"] == "ACEITE-1L"

        # 5. POST /ordenes-compra/12/devoluciones -> 201 y publica DevolucionProveedorRegistrada
        eventos_dev = []
        monkeypatch.setattr(
            repo_dev,
            "publicar_devolucion_registrada",
            lambda **kw: eventos_dev.append(kw) or "ev-dev",
        )
        cursor_dev_ok = FakeCursor(
            [
                dict(orden_borrador, estado="RECIBIDA"),
                [
                    {
                        "id_detalle": 30,
                        "id_orden": 12,
                        "sku": "ACEITE-1L",
                        "cantidad_pedida": Decimal("3.000"),
                        "cantidad_recibida": Decimal("3.000"),
                        "cantidad_devuelta": Decimal("0.000"),
                        "precio_unitario": Decimal("300.00"),
                    }
                ],
                {
                    "id_devolucion": 9,
                    "id_orden": 12,
                    "fecha": ahora,
                    "motivo": "Botella rota",
                    "id_usuario": 7,
                },
            ]
        )
        parchar_transaccion(monkeypatch, repo_dev, cursor_dev_ok)
        res_dev_ok = client.post(
            "/ordenes-compra/12/devoluciones",
            json={"motivo": "Botella rota", "items": [{"id_detalle": 30, "cantidad": 1}]},
            headers=auth_headers("jefe_bodega"),
        )
        assert res_dev_ok.status_code == 201
        assert res_dev_ok.get_json()["id_devolucion"] == 9
        assert eventos_dev[0]["items"] == [{"sku": "ACEITE-1L", "cantidad": Decimal("1.000")}]

    def test_datos_iniciales_ordenes_coherentes_e_idempotentes(self):
        from db import datos_iniciales as datos

        assert len(datos.ORDENES_INICIALES) == 5
        estados = {o["estado"] for o in datos.ORDENES_INICIALES}
        assert estados == {"RECIBIDA", "RECIBIDA_PARCIAL", "APROBADA", "BORRADOR", "ANULADA"}

        cursor_vacio = FakeCursor([None, None, None, None, None])
        insertadas = datos.insertar(cursor_vacio)
        assert insertadas == 5

        cursor_existente = FakeCursor([{"id_orden": 1}] * 5)
        assert datos.insertar(cursor_existente) == 0
