import json
import uuid
from decimal import Decimal
import requests

import pytest

from app import create_app
from app.clientes.productos_client import set_catalogo_mock
from app.db import abrir_conexion
from app.errors import ApiError
from app.repositorios.eventos_repo import procesar_evento

AUTH_HEADERS = {
    "Authorization": "Bearer token-test-2026",
    "X-User-Id": "1",
    "X-User-Role": "admin",
    "X-Correlation-Id": "corr-test-reportes-123",
}


@pytest.fixture(scope="module")
def app_cliente():
    app = create_app({
        "TESTING": True,
        "SERVICE_TOKEN": "token-test-2026",
    })
    with app.test_client() as client:
        yield client


@pytest.fixture(scope="module")
def db_conn():
    try:
        conn = abrir_conexion()
    except ApiError:
        pytest.skip("MySQL de desarrollo no disponible en 127.0.0.1:33065")
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def limpiar_tablas(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("DELETE FROM alerta_stock")
    cursor.execute("DELETE FROM movimiento_diario")
    cursor.execute("DELETE FROM orden_pendiente")
    cursor.execute("DELETE FROM saldo_reporte")
    cursor.execute("DELETE FROM evento_procesado")
    db_conn.commit()
    cursor.close()
    set_catalogo_mock(None)
    yield
    set_catalogo_mock(None)


def test_health_y_bloqueo_auth(app_cliente):
    # 1. Health público responde 200 sin token
    res = app_cliente.get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"

    # 2. Bloqueo 401 sin token de servicio
    res_val = app_cliente.get("/reportes/valorizacion")
    assert res_val.status_code == 401
    assert res_val.get_json()["error"]["codigo"] == "NO_AUTENTICADO"

    res_dash = app_cliente.get("/dashboard", headers={"Authorization": "Bearer token-invalido"})
    assert res_dash.status_code == 401
    assert res_dash.get_json()["error"]["codigo"] == "NO_AUTENTICADO"


def test_procesamiento_eventos_e_idempotencia_y_cierre_alerta(db_conn):
    # 1. StockBajoUmbral activa la alerta
    id_ev_stock = str(uuid.uuid4())
    ev_stock = {
        "id_evento": id_ev_stock,
        "tipo": "StockBajoUmbral",
        "fecha": "2026-11-18T01:00:00Z",
        "datos": {"sku": "SKU-ALERTA-1", "id_bodega": 1, "saldo": 2.0, "stock_minimo": 10.0},
    }
    r1 = procesar_evento(ev_stock, conexion=db_conn)
    assert r1["duplicado"] is False

    # Idempotencia: segundo envío es duplicado
    r1_dup = procesar_evento(ev_stock, conexion=db_conn)
    assert r1_dup["duplicado"] is True

    cursor = db_conn.cursor(dictionary=True)
    cursor.execute("SELECT activa, saldo, stock_minimo FROM alerta_stock WHERE sku = 'SKU-ALERTA-1'")
    alerta = cursor.fetchone()
    assert alerta["activa"] == 1
    assert Decimal(str(alerta["saldo"])) == Decimal("2.000")

    # 2. MovimientoRegistrado de salida (mantiene alerta activa porque saldo 1 <= 10)
    ev_mov_salida = {
        "id_evento": str(uuid.uuid4()),
        "tipo": "MovimientoRegistrado",
        "fecha": "2026-11-18T02:00:00Z",
        "datos": {
            "id_movimiento": 201,
            "sku": "SKU-ALERTA-1",
            "id_bodega": 1,
            "tipo": "SALIDA",
            "cantidad": 1.0,
            "costo_unitario": 1000.0,
            "saldo_resultante": 1.0,
            "costo_promedio": 1000.0,
            "valor_resultante": 1000.0,
        },
    }
    procesar_evento(ev_mov_salida, conexion=db_conn)
    cursor.execute("SELECT activa, saldo FROM alerta_stock WHERE sku = 'SKU-ALERTA-1'")
    alerta_salida = cursor.fetchone()
    assert alerta_salida["activa"] == 1
    assert Decimal(str(alerta_salida["saldo"])) == Decimal("1.000")

    # 3. MovimientoRegistrado de entrada que supera stock_minimo (saldo 15 > 10) -> apaga alerta
    ev_mov_entrada = {
        "id_evento": str(uuid.uuid4()),
        "tipo": "MovimientoRegistrado",
        "fecha": "2026-11-18T03:00:00Z",
        "datos": {
            "id_movimiento": 202,
            "sku": "SKU-ALERTA-1",
            "id_bodega": 1,
            "tipo": "ENTRADA_COMPRA",
            "cantidad": 14.0,
            "costo_unitario": 1000.0,
            "saldo_resultante": 15.0,
            "costo_promedio": 1000.0,
            "valor_resultante": 15000.0,
        },
    }
    procesar_evento(ev_mov_entrada, conexion=db_conn)
    cursor.execute("SELECT activa, saldo FROM alerta_stock WHERE sku = 'SKU-ALERTA-1'")
    alerta_recuperada = cursor.fetchone()
    assert alerta_recuperada["activa"] == 0  # Cierre automático verificado!
    assert Decimal(str(alerta_recuperada["saldo"])) == Decimal("15.000")

    # 4. OrdenCompraActualizada
    ev_orden = {
        "id_evento": str(uuid.uuid4()),
        "tipo": "OrdenCompraActualizada",
        "fecha": "2026-11-18T04:00:00Z",
        "datos": {
            "id_orden": 88,
            "numero": "OC-0088",
            "id_proveedor": 4,
            "estado": "APROBADA",
            "total": 120000.0,
        },
    }
    procesar_evento(ev_orden, conexion=db_conn)
    cursor.execute("SELECT * FROM orden_pendiente WHERE id_orden = 88")
    orden = cursor.fetchone()
    assert orden is not None
    assert orden["estado"] == "APROBADA"
    cursor.close()


def test_endpoint_valorizacion_agrupaciones(app_cliente, db_conn):
    # Población de prueba
    cursor = db_conn.cursor()
    cursor.execute(
        """
        INSERT INTO saldo_reporte (sku, id_bodega, cantidad, costo_promedio, valor_total)
        VALUES 
            ('SKU-A', 1, 10.0, 500.0, 5000.0),
            ('SKU-B', 1, 5.0, 2000.0, 10000.0),
            ('SKU-A', 2, 2.0, 500.0, 1000.0)
        """
    )
    db_conn.commit()
    cursor.close()

    mock_catalogo = {
        "SKU-A": {"nombre": "Producto Alfa", "id_categoria": 10, "categoria_nombre": "Lácteos"},
        "SKU-B": {"nombre": "Producto Beta", "id_categoria": 20, "categoria_nombre": "Bebidas"},
    }
    set_catalogo_mock(mock_catalogo)

    # 1. Por producto
    res_prod = app_cliente.get("/reportes/valorizacion?agrupar=producto", headers=AUTH_HEADERS)
    assert res_prod.status_code == 200
    json_prod = res_prod.get_json()
    assert json_prod["resumen"]["valor_total"] == 16000.0
    assert len(json_prod["data"]) == 3
    assert json_prod["data"][0]["nombre"] in ("Producto Alfa", "Producto Beta")

    # 2. Por bodega
    res_bod = app_cliente.get("/reportes/valorizacion?agrupar=bodega", headers=AUTH_HEADERS)
    assert res_bod.status_code == 200
    json_bod = res_bod.get_json()
    assert len(json_bod["data"]) == 2  # Bodegas 1 y 2
    bodega1 = next(b for b in json_bod["data"] if b["id_bodega"] == 1)
    assert bodega1["valor_total"] == 15000.0

    # 3. Por categoría
    res_cat = app_cliente.get("/reportes/valorizacion?agrupar=categoria", headers=AUTH_HEADERS)
    assert res_cat.status_code == 200
    json_cat = res_cat.get_json()
    assert len(json_cat["data"]) == 2
    lacteos = next(c for c in json_cat["data"] if c["categoria"] == "Lácteos")
    assert lacteos["cantidad_total"] == 12.0
    assert lacteos["valor_total"] == 6000.0


def test_endpoint_rotacion(app_cliente, db_conn):
    cursor = db_conn.cursor()
    cursor.execute(
        """
        INSERT INTO movimiento_diario (sku, id_bodega, fecha, entradas, salidas)
        VALUES 
            ('SKU-TOP', 1, '2026-11-15', 50.0, 45.0),
            ('SKU-SLOW', 1, '2026-11-15', 10.0, 1.0),
            ('SKU-MID', 1, '2026-11-16', 20.0, 15.0)
        """
    )
    db_conn.commit()
    cursor.close()

    res = app_cliente.get(
        "/reportes/rotacion?desde=2026-11-01&hasta=2026-11-30&top=2",
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["mayor_rotacion"]) == 2
    assert data["mayor_rotacion"][0]["sku"] == "SKU-TOP"
    assert data["mayor_rotacion"][0]["total_salidas"] == 45.0

    assert len(data["menor_rotacion"]) == 2
    assert data["menor_rotacion"][0]["sku"] == "SKU-SLOW"
    assert data["menor_rotacion"][0]["total_salidas"] == 1.0


def test_endpoint_stock_bajo(app_cliente, db_conn):
    cursor = db_conn.cursor()
    cursor.execute(
        """
        INSERT INTO alerta_stock (sku, id_bodega, saldo, stock_minimo, activa)
        VALUES 
            ('SKU-BAJO', 1, 3.0, 10.0, 1),
            ('SKU-INACTIVO', 1, 15.0, 10.0, 0)
        """
    )
    db_conn.commit()
    cursor.close()

    res = app_cliente.get("/reportes/stock-bajo?id_bodega=1", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.get_json()
    # Solo debe retornar las alertas con activa = 1
    assert len(data["data"]) == 1
    assert data["data"][0]["sku"] == "SKU-BAJO"
    assert data["data"][0]["diferencia"] == -7.0


def test_endpoint_dashboard(app_cliente, db_conn):
    cursor = db_conn.cursor()
    cursor.execute("INSERT INTO saldo_reporte (sku, id_bodega, cantidad, costo_promedio, valor_total) VALUES ('SKU-1', 1, 10, 100, 1000.0)")
    cursor.execute("INSERT INTO alerta_stock (sku, id_bodega, saldo, stock_minimo, activa) VALUES ('SKU-1', 1, 2, 5, 1)")
    cursor.execute("INSERT INTO orden_pendiente (id_orden, id_proveedor, estado, total) VALUES (1, 1, 'APROBADA', 5000.0)")
    cursor.execute("INSERT INTO movimiento_diario (sku, id_bodega, fecha, entradas, salidas) VALUES ('SKU-1', 1, '2026-11-18', 10, 8)")
    db_conn.commit()
    cursor.close()

    res = app_cliente.get("/dashboard", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.get_json()

    # Comprobación estricta de las 5 llaves exactas de la Tabla 10
    llaves_esperadas = {
        "valor_total_inventario",
        "productos_stock_bajo",
        "ordenes_pendientes",
        "mayor_rotacion",
        "menor_rotacion",
    }
    assert set(data.keys()) == llaves_esperadas
    assert data["valor_total_inventario"] == 1000.0
    assert data["productos_stock_bajo"] == 1
    assert data["ordenes_pendientes"] == 1
    assert isinstance(data["mayor_rotacion"], list)
    assert isinstance(data["menor_rotacion"], list)


def test_exportacion_formatos_csv_y_pdf(app_cliente, db_conn):
    cursor = db_conn.cursor()
    cursor.execute("INSERT INTO saldo_reporte (sku, id_bodega, cantidad, costo_promedio, valor_total) VALUES ('SKU-EXP', 1, 10, 200, 2000.0)")
    cursor.execute("INSERT INTO movimiento_diario (sku, id_bodega, fecha, entradas, salidas) VALUES ('SKU-EXP', 1, '2026-11-18', 10, 5)")
    cursor.execute("INSERT INTO alerta_stock (sku, id_bodega, saldo, stock_minimo, activa) VALUES ('SKU-EXP', 1, 1, 5, 1)")
    db_conn.commit()
    cursor.close()

    # 1. Valorización CSV y PDF
    res_val_csv = app_cliente.get("/reportes/valorizacion?formato=csv", headers=AUTH_HEADERS)
    assert res_val_csv.status_code == 200
    assert "text/csv" in res_val_csv.headers["Content-Type"]
    assert b"SKU,Nombre" in res_val_csv.data

    res_val_pdf = app_cliente.get("/reportes/valorizacion?formato=pdf", headers=AUTH_HEADERS)
    assert res_val_pdf.status_code == 200
    assert "application/pdf" in res_val_pdf.headers["Content-Type"]
    assert res_val_pdf.data.startswith(b"%PDF")

    # 2. Rotación CSV y PDF
    res_rot_csv = app_cliente.get("/reportes/rotacion?formato=csv", headers=AUTH_HEADERS)
    assert res_rot_csv.status_code == 200
    assert "text/csv" in res_rot_csv.headers["Content-Type"]

    res_rot_pdf = app_cliente.get("/reportes/rotacion?formato=pdf", headers=AUTH_HEADERS)
    assert res_rot_pdf.status_code == 200
    assert "application/pdf" in res_rot_pdf.headers["Content-Type"]
    assert res_rot_pdf.data.startswith(b"%PDF")

    # 3. Stock Bajo CSV y PDF
    res_stk_csv = app_cliente.get("/reportes/stock-bajo?formato=csv", headers=AUTH_HEADERS)
    assert res_stk_csv.status_code == 200
    assert "text/csv" in res_stk_csv.headers["Content-Type"]

    res_stk_pdf = app_cliente.get("/reportes/stock-bajo?formato=pdf", headers=AUTH_HEADERS)
    assert res_stk_pdf.status_code == 200
    assert "application/pdf" in res_stk_pdf.headers["Content-Type"]
    assert res_stk_pdf.data.startswith(b"%PDF")


def test_validaciones_422_parametros_invalidos(app_cliente):
    # Parámetro agrupar inválido
    r1 = app_cliente.get("/reportes/valorizacion?agrupar=invalido", headers=AUTH_HEADERS)
    assert r1.status_code == 422
    assert r1.get_json()["error"]["codigo"] == "VALIDACION"

    # Parámetro formato inválido
    r2 = app_cliente.get("/reportes/valorizacion?formato=xml", headers=AUTH_HEADERS)
    assert r2.status_code == 422

    # id_bodega no entero
    r3 = app_cliente.get("/reportes/valorizacion?id_bodega=abc", headers=AUTH_HEADERS)
    assert r3.status_code == 422

    # Rango de fechas incongruente (desde > hasta)
    r4 = app_cliente.get("/reportes/rotacion?desde=2026-11-20&hasta=2026-11-10", headers=AUTH_HEADERS)
    assert r4.status_code == 422
    assert "desde" in r4.get_json()["error"]["detalles"]

    # top menor a 1
    r5 = app_cliente.get("/reportes/rotacion?top=0", headers=AUTH_HEADERS)
    assert r5.status_code == 422

    # Fecha con formato no ISO
    r6 = app_cliente.get("/reportes/rotacion?desde=20-11-2026", headers=AUTH_HEADERS)
    assert r6.status_code == 422


def test_error_503_cuando_ms_productos_no_responde_en_categoria(app_cliente):
    # Simulamos falla de red/timeout en ms-productos
    set_catalogo_mock(requests.RequestException("Fallo de conexión simulado"))

    # Al agrupar por categoría es obligatorio: responde 503
    res_cat = app_cliente.get("/reportes/valorizacion?agrupar=categoria", headers=AUTH_HEADERS)
    assert res_cat.status_code == 503
    data_cat = res_cat.get_json()
    assert data_cat["error"]["codigo"] == "SERVICIO_NO_DISPONIBLE"

    # En modo producto es tolerante: no lanza 503, usa fallback
    res_prod = app_cliente.get("/reportes/valorizacion?agrupar=producto", headers=AUTH_HEADERS)
    assert res_prod.status_code == 200
