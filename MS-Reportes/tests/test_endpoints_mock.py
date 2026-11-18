"""Pruebas unitarias exhaustivas con mocking para MS-Reportes.

Cubre recepcion, validacion, manejo de errores, proyecciones de eventos,
cliente HTTP a ms-productos, consumidor RabbitMQ, datos iniciales y exportacion
CSV/PDF para todos los endpoints, sin depender de MySQL ni RabbitMQ reales,
incluyendo casos verdaderos, absurdos, ilogicos y fuera de rango.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import json
from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid

import mysql.connector
import pytest
import requests

import app.clientes.productos_client as productos_client
from app.clientes.productos_client import obtener_catalogo_productos, set_catalogo_mock
import app.consumidor as consumidor
from app.db import set_transaccion_override
from app.errors import ApiError
import app.repositorios.eventos_repo as eventos_repo
import app.routes.reportes_routes as rutas_reportes
from app.validacion import Errores, entero_opcional
from app import create_app
from db import datos_iniciales

TOKEN = "token-unitario-reportes-2026"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "X-User-Id": "1",
    "X-User-Role": "admin",
}

CATALOGO_EJEMPLO = {
    "LAC-0001": {"nombre": "Leche entera 1100 ml", "id_categoria": 10, "categoria_nombre": "Lacteos"},
    "BEB-0001": {"nombre": "Gaseosa 1.5 L", "id_categoria": 20, "categoria_nombre": "Bebidas"},
    "PAN-0001": {"nombre": "Pan tajado 600 g", "id_categoria": 30, "categoria_nombre": "Panaderia"},
}


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "SERVICE_TOKEN": TOKEN})
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def limpiar_mocks(monkeypatch):
    set_transaccion_override(None)
    set_catalogo_mock(None)
    monkeypatch.delenv("STRICT_PRODUCTS_CHECK", raising=False)
    yield
    set_transaccion_override(None)
    set_catalogo_mock(None)


def mock_transaccion(monkeypatch, cursor=None):
    """Reemplaza transaccion() usando set_transaccion_override con registro de estado."""
    estado = {"commits": 0, "rollbacks": 0, "cursor": cursor if cursor is not None else MagicMock()}

    @contextmanager
    def _tx(_config=None):
        try:
            yield estado["cursor"]
            estado["commits"] += 1
        except Exception:
            estado["rollbacks"] += 1
            raise

    set_transaccion_override(_tx)
    return estado


class FakeConexionEventos:
    """Simula una conexion MySQL para probar eventos_repo.procesar_evento."""

    def __init__(self, resultados_fetchone=None, lanzar_en_execute=None):
        self._resultados = list(resultados_fetchone or [None])
        self._lanzar = lanzar_en_execute
        self.ejecutadas = []
        self.commits = 0
        self.rollbacks = 0
        self.cerrada = False
        self.in_transaction = False

    def cursor(self, dictionary=True):
        return _FakeCursorEventos(self, dictionary=dictionary)

    def start_transaction(self):
        self.in_transaction = True

    def commit(self):
        self.commits += 1
        self.in_transaction = False

    def rollback(self):
        self.rollbacks += 1
        self.in_transaction = False

    def close(self):
        self.cerrada = True


class _FakeCursorEventos:
    def __init__(self, conn, dictionary=True):
        self._conn = conn
        self.dictionary = dictionary

    def execute(self, sql, params=None):
        if self._conn._lanzar is not None:
            raise self._conn._lanzar
        self._conn.ejecutadas.append((" ".join(sql.split()), params))

    def fetchone(self):
        if self._conn._resultados:
            return self._conn._resultados.pop(0)
        return None

    def close(self):
        pass


class TestSeguridadYErroresTransversales:
    def test_arranque_falla_sin_service_token_o_token_de_ejemplo(self, monkeypatch):
        monkeypatch.setattr("app.config.cargar_configuracion", lambda: {"SERVICE_TOKEN": ""})
        with pytest.raises(RuntimeError):
            create_app({"TESTING": True, "SERVICE_TOKEN": ""})

        with pytest.raises(RuntimeError):
            create_app({"TESTING": True, "SERVICE_TOKEN": "cambia-este-token"})

    @pytest.mark.parametrize(
        "ruta",
        [
            "/reportes/valorizacion",
            "/reportes/rotacion",
            "/reportes/stock-bajo",
            "/dashboard",
        ],
    )
    @pytest.mark.parametrize(
        "headers",
        [
            {},
            {"Authorization": "Basic dXNlcjpwYXNz"},
            {"Authorization": "Bearer "},
            {"Authorization": "Bearer token-incorrecto"},
            {"Authorization": TOKEN},
        ],
    )
    def test_rechaza_401_en_rutas_protegidas(self, client, ruta, headers):
        res = client.get(ruta, headers=headers)
        assert res.status_code == 401
        body = res.get_json()
        assert body["error"]["codigo"] == "NO_AUTENTICADO"

    def test_health_publico_y_trazabilidad_correlation_id(self, client, monkeypatch):
        res_health = client.get("/health")
        assert res_health.status_code == 200
        assert res_health.get_json()["status"] == "ok"
        assert res_health.headers.get("X-Correlation-Id")

        corr = "corr-traza-reportes-001"
        mock_transaccion(monkeypatch)
        set_catalogo_mock({})
        monkeypatch.setattr(
            rutas_reportes.repo,
            "obtener_metricas_dashboard",
            lambda _c: {
                "valor_total_inventario": 0.0,
                "productos_stock_bajo": 0,
                "ordenes_pendientes": 0,
                "mayor_rotacion": [],
                "menor_rotacion": [],
            },
        )
        res_dash = client.get("/dashboard", headers={**HEADERS, "X-Correlation-Id": corr})
        assert res_dash.status_code == 200
        assert res_dash.headers.get("X-Correlation-Id") == corr

    def test_404_405_500_y_503_db_ocultan_detalles_internos(self, client, monkeypatch):
        res_404 = client.get("/reportes/no-existe", headers=HEADERS)
        assert res_404.status_code == 404
        assert res_404.get_json()["error"]["codigo"] == "NO_EXISTE"

        res_405 = client.post("/dashboard", headers=HEADERS)
        assert res_405.status_code == 405
        assert res_405.get_json()["error"]["codigo"] == "METODO_NO_PERMITIDO"
        assert "GET" in res_405.headers.get("Allow", "")

        mock_transaccion(monkeypatch)
        monkeypatch.setattr(
            rutas_reportes.repo,
            "obtener_metricas_dashboard",
            MagicMock(side_effect=RuntimeError("secreto_stacktrace_interno")),
        )
        res_500 = client.get("/dashboard", headers=HEADERS)
        assert res_500.status_code == 500
        cuerpo_500 = res_500.get_json()
        assert cuerpo_500["error"]["codigo"] == "ERROR_INTERNO"
        assert "secreto_stacktrace_interno" not in json.dumps(cuerpo_500)

        set_transaccion_override(None)
        monkeypatch.setattr(
            "app.db.mysql.connector.connect",
            MagicMock(side_effect=mysql.connector.Error(msg="Access denied for user secret_root")),
        )
        res_503 = client.get("/dashboard", headers=HEADERS)
        assert res_503.status_code == 503
        cuerpo_503 = res_503.get_json()
        assert cuerpo_503["error"]["codigo"] == "SERVICIO_NO_DISPONIBLE"
        assert "secret_root" not in json.dumps(cuerpo_503)


class TestReporteValorizacionMock:
    def test_valorizacion_por_producto_categoria_bodega_paginado_y_compatibilidad_frontend(
        self, client, monkeypatch
    ):
        estado = mock_transaccion(monkeypatch)
        set_catalogo_mock(CATALOGO_EJEMPLO)

        ahora = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)
        filas_producto = [
            {
                "sku": "LAC-0001",
                "id_bodega": 1,
                "cantidad": Decimal("100.000"),
                "costo_promedio": Decimal("3450.0000"),
                "valor_total": Decimal("345000.00"),
                "actualizado_en": ahora,
            },
            {
                "sku": "BEB-0001",
                "id_bodega": 1,
                "cantidad": Decimal("50.000"),
                "costo_promedio": Decimal("4600.0000"),
                "valor_total": Decimal("230000.00"),
                "actualizado_en": ahora,
            },
        ]
        monkeypatch.setattr(
            rutas_reportes.repo,
            "obtener_totales_valorizacion",
            lambda _c, id_bodega=None: {"cantidad_total": Decimal("150.000"), "valor_total": Decimal("575000.00")},
        )
        monkeypatch.setattr(
            rutas_reportes.repo,
            "obtener_valorizacion_por_producto",
            lambda _c, id_bodega=None: filas_producto,
        )

        # 1. Agrupado por producto con paginacion
        res_prod = client.get("/reportes/valorizacion?agrupar=producto&page=1&per_page=1", headers=HEADERS)
        assert res_prod.status_code == 200
        body_prod = res_prod.get_json()
        assert estado["commits"] == 1
        assert body_prod["meta"] == {"page": 1, "per_page": 1, "total": 2}
        assert body_prod["resumen"] == {"cantidad_total": 150.0, "valor_total": 575000.0}
        item = body_prod["data"][0]
        assert item["sku"] == "LAC-0001"
        assert item["clave"] == "LAC-0001-1"
        assert item["valor"] == 345000.0
        assert item["valor_total"] == 345000.0

        # 2. Agrupado por categoria
        res_cat = client.get("/reportes/valorizacion?agrupar=categoria&id_bodega=1", headers=HEADERS)
        assert res_cat.status_code == 200
        data_cat = res_cat.get_json()["data"]
        assert len(data_cat) == 2
        assert data_cat[0]["clave"] == "10"
        assert data_cat[0]["nombre"] == "Lacteos"
        assert data_cat[0]["categoria"] == "Lacteos"
        assert data_cat[0]["valor"] == 345000.0
        assert data_cat[0]["valor_total"] == 345000.0

        # 3. Agrupado por bodega
        monkeypatch.setattr(
            rutas_reportes.repo,
            "obtener_valorizacion_por_bodega",
            lambda _c, id_bodega=None: [
                {
                    "id_bodega": 1,
                    "total_productos": 2,
                    "cantidad_total": Decimal("150.000"),
                    "valor_total": Decimal("575000.00"),
                }
            ],
        )
        res_bod = client.get("/reportes/valorizacion?agrupar=bodega", headers=HEADERS)
        assert res_bod.status_code == 200
        data_bod = res_bod.get_json()["data"]
        assert data_bod[0]["id_bodega"] == 1
        assert data_bod[0]["clave"] == "1"
        assert data_bod[0]["cantidad"] == 150.0
        assert data_bod[0]["valor"] == 575000.0

    def test_valorizacion_exporta_csv_y_pdf_para_cada_agrupacion(self, client, monkeypatch):
        mock_transaccion(monkeypatch)
        set_catalogo_mock(CATALOGO_EJEMPLO)
        monkeypatch.setattr(
            rutas_reportes.repo,
            "obtener_totales_valorizacion",
            lambda _c, id_bodega=None: {"cantidad_total": Decimal("10.000"), "valor_total": Decimal("34500.00")},
        )
        monkeypatch.setattr(
            rutas_reportes.repo,
            "obtener_valorizacion_por_producto",
            lambda _c, id_bodega=None: [
                {
                    "sku": "LAC-0001",
                    "id_bodega": 1,
                    "cantidad": Decimal("10.000"),
                    "costo_promedio": Decimal("3450.0000"),
                    "valor_total": Decimal("34500.00"),
                    "actualizado_en": "2026-11-18T12:00:00Z",
                }
            ],
        )
        monkeypatch.setattr(
            rutas_reportes.repo,
            "obtener_valorizacion_por_bodega",
            lambda _c, id_bodega=None: [],
        )

        for agrupar in ("producto", "categoria", "bodega"):
            res_csv = client.get(f"/reportes/valorizacion?agrupar={agrupar}&formato=csv", headers=HEADERS)
            assert res_csv.status_code == 200
            assert "text/csv" in res_csv.headers["Content-Type"]
            assert "reporte_valorizacion.csv" in res_csv.headers["Content-Disposition"]

            res_pdf = client.get(f"/reportes/valorizacion?agrupar={agrupar}&formato=pdf", headers=HEADERS)
            assert res_pdf.status_code == 200
            assert "application/pdf" in res_pdf.headers["Content-Type"]
            assert res_pdf.data.startswith(b"%PDF")

    def test_valorizacion_dependencia_ms_productos_503_y_fallback(self, client, monkeypatch):
        mock_transaccion(monkeypatch)
        monkeypatch.setattr(
            rutas_reportes.repo,
            "obtener_totales_valorizacion",
            lambda _c, id_bodega=None: {"cantidad_total": Decimal("1.000"), "valor_total": Decimal("100.00")},
        )
        monkeypatch.setattr(
            rutas_reportes.repo,
            "obtener_valorizacion_por_producto",
            lambda _c, id_bodega=None: [
                {
                    "sku": "SIN-CAT",
                    "id_bodega": 1,
                    "cantidad": Decimal("1.000"),
                    "costo_promedio": Decimal("100.0000"),
                    "valor_total": Decimal("100.00"),
                    "actualizado_en": "2026-11-18T12:00:00Z",
                }
            ],
        )
        set_catalogo_mock(requests.Timeout("Timeout hacia ms-productos"))

        res_cat = client.get("/reportes/valorizacion?agrupar=categoria", headers=HEADERS)
        assert res_cat.status_code == 503
        assert res_cat.get_json()["error"]["codigo"] == "SERVICIO_NO_DISPONIBLE"

        res_prod = client.get("/reportes/valorizacion?agrupar=producto", headers=HEADERS)
        assert res_prod.status_code == 200
        assert res_prod.get_json()["data"][0]["nombre"] == "SIN-CAT"

    @pytest.mark.parametrize(
        "query,campo",
        [
            ("agrupar=proveedor", "agrupar"),
            ("agrupar=123", "agrupar"),
            ("formato=xlsx", "formato"),
            ("formato=exe", "formato"),
            ("id_bodega=0", "id_bodega"),
            ("id_bodega=-7", "id_bodega"),
            ("id_bodega=abc", "id_bodega"),
            ("id_bodega=1.5", "id_bodega"),
            ("id_bodega=2147483648", "id_bodega"),
            ("page=0", "page"),
            ("page=-5", "page"),
            ("page=uno", "page"),
            ("page=2147483648", "page"),
            ("per_page=0", "per_page"),
            ("per_page=-1", "per_page"),
            ("per_page=101", "per_page"),
            ("per_page=mil", "per_page"),
        ],
    )
    def test_valorizacion_rechaza_422_casos_absurdos_e_ilogicos(self, client, monkeypatch, query, campo):
        mock_transaccion(monkeypatch)
        monkeypatch.setattr(
            rutas_reportes.repo,
            "obtener_totales_valorizacion",
            lambda _c, id_bodega=None: {"cantidad_total": Decimal("0"), "valor_total": Decimal("0")},
        )
        monkeypatch.setattr(
            rutas_reportes.repo,
            "obtener_valorizacion_por_producto",
            lambda _c, id_bodega=None: [],
        )
        set_catalogo_mock({})

        res = client.get(f"/reportes/valorizacion?{query}", headers=HEADERS)
        assert res.status_code == 422
        body = res.get_json()
        assert body["error"]["codigo"] == "VALIDACION"
        assert campo in body["error"]["detalles"]


class TestReporteRotacionYStockBajoYDashboardMock:
    def test_rotacion_calculo_top_csv_pdf_y_campos_frontend(self, client, monkeypatch):
        mock_transaccion(monkeypatch)
        set_catalogo_mock(CATALOGO_EJEMPLO)
        monkeypatch.setattr(
            rutas_reportes.repo,
            "obtener_rotacion",
            lambda _c, desde=None, hasta=None, id_bodega=None: [
                {"sku": "LAC-0001", "total_entradas": Decimal("20.000"), "total_salidas": Decimal("45.000")},
                {"sku": "BEB-0001", "total_entradas": Decimal("10.000"), "total_salidas": Decimal("2.000")},
                {"sku": "PAN-0001", "total_entradas": Decimal("30.000"), "total_salidas": Decimal("18.000")},
            ],
        )

        res = client.get("/reportes/rotacion?desde=2026-11-01&hasta=2026-11-18&id_bodega=2&top=2", headers=HEADERS)
        assert res.status_code == 200
        body = res.get_json()
        assert body["desde"] == "2026-11-01"
        assert body["hasta"] == "2026-11-18"
        assert len(body["mayor_rotacion"]) == 2
        assert body["mayor_rotacion"][0]["sku"] == "LAC-0001"
        assert body["mayor_rotacion"][0]["unidades_salida"] == 45.0
        assert body["mayor_rotacion"][0]["rotacion"] == 45.0
        assert body["menor_rotacion"][0]["sku"] == "BEB-0001"

        res_csv = client.get("/reportes/rotacion?formato=csv", headers=HEADERS)
        assert res_csv.status_code == 200
        assert "text/csv" in res_csv.headers["Content-Type"]

        res_pdf = client.get("/reportes/rotacion?formato=pdf", headers=HEADERS)
        assert res_pdf.status_code == 200
        assert res_pdf.data.startswith(b"%PDF")

    @pytest.mark.parametrize(
        "query,campo",
        [
            ("desde=2026-11-25&hasta=2026-11-01", "desde"),
            ("desde=2026-02-30", "desde"),
            ("desde=18-11-2026", "desde"),
            ("hasta=ayer", "hasta"),
            ("hasta=2026-13-01", "hasta"),
            ("top=0", "top"),
            ("top=-3", "top"),
            ("top=muchos", "top"),
            ("top=2.5", "top"),
            ("top=2147483648", "top"),
            ("id_bodega=0", "id_bodega"),
            ("id_bodega=-1", "id_bodega"),
            ("formato=doc", "formato"),
        ],
    )
    def test_rotacion_rechaza_422_casos_absurdos_e_ilogicos(self, client, query, campo):
        res = client.get(f"/reportes/rotacion?{query}", headers=HEADERS)
        assert res.status_code == 422
        body = res.get_json()
        assert body["error"]["codigo"] == "VALIDACION"
        assert campo in body["error"]["detalles"]

    def test_stock_bajo_json_paginado_csv_pdf_y_422(self, client, monkeypatch):
        mock_transaccion(monkeypatch)
        set_catalogo_mock(CATALOGO_EJEMPLO)
        monkeypatch.setattr(
            rutas_reportes.repo,
            "obtener_alertas_stock_bajo",
            lambda _c, id_bodega=None: [
                {
                    "sku": "BEB-0001",
                    "id_bodega": 2,
                    "saldo": Decimal("25.000"),
                    "stock_minimo": Decimal("30.000"),
                    "diferencia": Decimal("-5.000"),
                    "fecha": datetime(2026, 11, 18, 10, 0, 0, tzinfo=timezone.utc),
                    "activa": 1,
                },
                {
                    "sku": "PAN-0001",
                    "id_bodega": 2,
                    "saldo": Decimal("12.000"),
                    "stock_minimo": Decimal("15.000"),
                    "diferencia": Decimal("-3.000"),
                    "fecha": datetime(2026, 11, 18, 10, 0, 0, tzinfo=timezone.utc),
                    "activa": 1,
                },
            ],
        )

        res = client.get("/reportes/stock-bajo?id_bodega=2&page=1&per_page=1", headers=HEADERS)
        assert res.status_code == 200
        body = res.get_json()
        assert body["meta"] == {"page": 1, "per_page": 1, "total": 2}
        assert body["data"][0]["sku"] == "BEB-0001"
        assert body["data"][0]["diferencia"] == -5.0
        assert body["data"][0]["activa"] is True

        res_csv = client.get("/reportes/stock-bajo?formato=csv", headers=HEADERS)
        assert res_csv.status_code == 200
        assert b"BEB-0001" in res_csv.data

        res_pdf = client.get("/reportes/stock-bajo?formato=pdf", headers=HEADERS)
        assert res_pdf.status_code == 200
        assert res_pdf.data.startswith(b"%PDF")

        for malo in ("id_bodega=0", "id_bodega=-9", "id_bodega=xyz", "formato=yaml", "per_page=101", "page=0"):
            res_err = client.get(f"/reportes/stock-bajo?{malo}", headers=HEADERS)
            assert res_err.status_code == 422

    def test_dashboard_con_y_sin_bodega_y_422_ilogico(self, client, monkeypatch):
        mock_transaccion(monkeypatch)
        set_catalogo_mock(CATALOGO_EJEMPLO)
        llamadas = []

        def _fake_metricas(_cursor, id_bodega=None):
            llamadas.append(id_bodega)
            return {
                "valor_total_inventario": 950000.0,
                "productos_stock_bajo": 2,
                "ordenes_pendientes": 3,
                "mayor_rotacion": [{"sku": "LAC-0001", "total_entradas": Decimal("50"), "total_salidas": Decimal("24")}],
                "menor_rotacion": [{"sku": "PAN-0001", "total_entradas": Decimal("30"), "total_salidas": Decimal("2")}],
            }

        monkeypatch.setattr(rutas_reportes.repo, "obtener_metricas_dashboard", _fake_metricas)

        res_global = client.get("/dashboard", headers=HEADERS)
        assert res_global.status_code == 200
        data_global = res_global.get_json()
        assert set(data_global.keys()) == {
            "valor_total_inventario",
            "productos_stock_bajo",
            "ordenes_pendientes",
            "mayor_rotacion",
            "menor_rotacion",
        }
        assert data_global["mayor_rotacion"][0]["rotacion"] == 24.0
        assert data_global["mayor_rotacion"][0]["unidades_salida"] == 24.0

        res_bod = client.get("/dashboard?id_bodega=2", headers=HEADERS)
        assert res_bod.status_code == 200
        assert llamadas[-1] == 2

        for malo in ("id_bodega=0", "id_bodega=-1", "id_bodega=todas", "id_bodega=9999999999"):
            res_malo = client.get(f"/dashboard?{malo}", headers=HEADERS)
            assert res_malo.status_code == 422
            assert res_malo.get_json()["error"]["codigo"] == "VALIDACION"

    def test_validador_entero_opcional_rechaza_booleanos_y_overflow(self):
        errores = Errores()
        entero_opcional(errores, {"a": True, "b": "1.5", "c": "2147483648"}, "a", minimo=1)
        entero_opcional(errores, {"a": True, "b": "1.5", "c": "2147483648"}, "b", minimo=1)
        entero_opcional(errores, {"a": True, "b": "1.5", "c": "2147483648"}, "c", minimo=1)
        assert set(errores.detalles.keys()) == {"a", "b", "c"}


class TestClienteProductosConsumidorEventosYDatosIniciales:
    def test_cliente_productos_http_mock_exitoso_y_fallos(self, monkeypatch):
        resp_cats = SimpleNamespace(
            status_code=200,
            json=lambda: {"data": [{"id_categoria": 5, "nombre": "Lacteos"}]},
        )
        resp_prods = SimpleNamespace(
            status_code=200,
            json=lambda: {"data": [{"sku": "LAC-0001", "nombre": "Leche", "id_categoria": 5}]},
        )
        llamadas_url = []

        def _fake_get(url, headers=None, timeout=None):
            llamadas_url.append((url, headers, timeout))
            if "/categorias" in url:
                return resp_cats
            return resp_prods

        monkeypatch.setattr(productos_client.requests, "get", _fake_get)
        cfg = {"PRODUCTOS_URL": "http://ms-productos:5000", "SERVICE_TOKEN": TOKEN}
        catalogo = obtener_catalogo_productos(requerido=True, config=cfg)
        assert catalogo["LAC-0001"] == {"nombre": "Leche", "id_categoria": 5, "categoria_nombre": "Lacteos"}
        assert len(llamadas_url) == 2

        # Fallo de red en modo estricto -> 503; en modo tolerante -> {}
        monkeypatch.setattr(productos_client.requests, "get", MagicMock(side_effect=requests.ConnectionError("down")))
        with pytest.raises(ApiError) as exc:
            obtener_catalogo_productos(requerido=True, config=cfg)
        assert exc.value.status == 503
        assert obtener_catalogo_productos(requerido=False, config=cfg) == {}

    @pytest.mark.parametrize(
        "tipo_mov,espera_entrada",
        [
            ("ENTRADA_COMPRA", True),
            ("AJUSTE_POSITIVO", True),
            ("TRASLADO_ENTRADA", True),
            ("DEVOLUCION_CLIENTE", True),
            ("SALIDA", False),
            ("AJUSTE_NEGATIVO", False),
            ("TRASLADO_SALIDA", False),
            ("DEVOLUCION_PROVEEDOR", False),
        ],
    )
    def test_eventos_repo_ocho_tipos_movimiento(self, tipo_mov, espera_entrada):
        conn = FakeConexionEventos([None])
        ev = {
            "id_evento": str(uuid.uuid4()),
            "tipo": "MovimientoRegistrado",
            "fecha": "2026-11-18T14:00:00Z",
            "datos": {
                "sku": "LAC-0001",
                "id_bodega": 1,
                "tipo": tipo_mov,
                "cantidad": 5,
                "costo_unitario": 3450,
                "saldo_resultante": 20,
                "costo_promedio": 3450,
                "valor_resultante": 69000,
            },
        }
        res = eventos_repo.procesar_evento(ev, conexion=conn)
        assert res["procesado"] is True
        assert conn.commits == 1
        sqls = [s for s, _ in conn.ejecutadas]
        assert any("INSERT INTO saldo_reporte" in s for s in sqls)
        assert any("INSERT INTO movimiento_diario" in s for s in sqls)
        assert any("UPDATE alerta_stock" in s for s in sqls)
        assert any("INSERT INTO evento_procesado" in s for s in sqls)
        sql_diario = next(p for s, p in conn.ejecutadas if "INSERT INTO movimiento_diario" in s)
        assert len(sql_diario) == 4
        if espera_entrada:
            assert "VALUES (%s, %s, %s, %s, 0.000)" in next(
                s for s, _ in conn.ejecutadas if "INSERT INTO movimiento_diario" in s
            )
        else:
            assert "VALUES (%s, %s, %s, 0.000, %s)" in next(
                s for s, _ in conn.ejecutadas if "INSERT INTO movimiento_diario" in s
            )

    def test_eventos_repo_idempotencia_y_entradas_absurdas(self):
        # Ya procesado -> duplicado True sin insertar nada
        conn_dup = FakeConexionEventos([{"1": 1}])
        res_dup = eventos_repo.procesar_evento(
            {"id_evento": "ev-ya-procesado", "tipo": "StockBajoUmbral", "datos": {}},
            conexion=conn_dup,
        )
        assert res_dup == {"duplicado": True, "id_evento": "ev-ya-procesado"}
        assert conn_dup.commits == 0

        # Casos absurdos e incompletos -> ValueError y rollback
        casos_malos = [
            "no-soy-un-dict",
            {"tipo": "StockBajoUmbral", "datos": {}},
            {"id_evento": "1", "datos": {}},
            {"id_evento": "1", "tipo": "StockBajoUmbral", "datos": "no-dict"},
            {"id_evento": "1", "tipo": "EventoInventado", "datos": {}},
            {"id_evento": "1", "tipo": "StockBajoUmbral", "datos": {"sku": "", "id_bodega": 1, "saldo": 1, "stock_minimo": 5}},
            {"id_evento": "1", "tipo": "OrdenCompraActualizada", "datos": {"id_orden": 1, "id_proveedor": 1, "estado": "  "}},
            {
                "id_evento": "1",
                "tipo": "MovimientoRegistrado",
                "datos": {
                    "sku": "X",
                    "id_bodega": 1,
                    "tipo": "TIPO_ABSURDO",
                    "cantidad": 1,
                    "costo_unitario": 10,
                    "saldo_resultante": 1,
                    "costo_promedio": 10,
                    "valor_resultante": 10,
                },
            },
        ]
        for payload in casos_malos:
            conn = FakeConexionEventos([None])
            with pytest.raises(ValueError):
                eventos_repo.procesar_evento(payload, conexion=conn)
            assert conn.commits == 0

    def test_consumidor_amqp_ack_y_reject_con_requeue(self, monkeypatch):
        ch = MagicMock()
        method = SimpleNamespace(delivery_tag=99)

        # Exito -> basic_ack
        monkeypatch.setattr(consumidor, "procesar_evento", lambda _p: {"duplicado": False, "procesado": True})
        body_ok = json.dumps({"id_evento": "ev-1", "tipo": "StockBajoUmbral", "datos": {}}).encode("utf-8")
        consumidor.procesar_mensaje_amqp(ch, method, None, body_ok)
        ch.basic_ack.assert_called_once_with(delivery_tag=99)

        # Error de BD transitorio -> basic_reject(requeue=True)
        ch.reset_mock()
        monkeypatch.setattr(consumidor, "procesar_evento", MagicMock(side_effect=ApiError("DB", "caida", 503)))
        consumidor.procesar_mensaje_amqp(ch, method, None, body_ok)
        ch.basic_reject.assert_called_once_with(delivery_tag=99, requeue=True)
        ch.basic_ack.assert_not_called()

        # Payload absurdo / JSON corrupto -> basic_reject(requeue=True)
        ch.reset_mock()
        consumidor.procesar_mensaje_amqp(ch, method, None, b"{corrupto")
        ch.basic_reject.assert_called_once_with(delivery_tag=99, requeue=True)

    def test_datos_iniciales_coherentes_e_idempotentes(self, monkeypatch):
        proyecciones = datos_iniciales._construir_proyecciones()
        # 33 productos x 2 bodegas (principal y sala) + 17 productos en bodega norte = 83
        assert len(proyecciones) == 83
        # BEB-0001 y PAN-0001 quedan bajo el stock minimo en bodega 2 (BOD-SALA)
        assert proyecciones[("BEB-0001", 2)][0] == Decimal("25")
        assert proyecciones[("PAN-0001", 2)][0] == Decimal("12")

        class CursorDatos:
            def __init__(self, n_saldos=0):
                self.n_saldos = n_saldos
                self.ejecutadas = []

            def execute(self, sql, params=None):
                self.ejecutadas.append((sql, params))

            def fetchone(self):
                return {"n": self.n_saldos}

            def fetchall(self):
                return []

        cursor_vacio = CursorDatos(n_saldos=0)
        saldos, alertas, ordenes = datos_iniciales.insertar(cursor_vacio, fecha_mov="2026-11-18")
        assert saldos == 83
        assert alertas == 2
        assert ordenes == 5

        @contextmanager
        def _tx_no_vacia(_cfg=None):
            yield CursorDatos(n_saldos=83)

        monkeypatch.setattr(datos_iniciales, "transaccion", _tx_no_vacia)
        assert datos_iniciales.sembrar({"DB_HOST": "x"}) is None
