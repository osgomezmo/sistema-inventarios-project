import json
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.db import abrir_conexion
from app.errors import ApiError
from app.consumidor import procesar_mensaje_amqp
from app.repositorios.eventos_repo import procesar_evento


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
    # Limpia las tablas antes de cada prueba para mantener aislamiento
    cursor = db_conn.cursor()
    cursor.execute("DELETE FROM alerta_stock")
    cursor.execute("DELETE FROM movimiento_diario")
    cursor.execute("DELETE FROM orden_pendiente")
    cursor.execute("DELETE FROM saldo_reporte")
    cursor.execute("DELETE FROM evento_procesado")
    db_conn.commit()
    cursor.close()
    yield


def test_stock_bajo_umbral_y_alerta(db_conn):
    id_evento = str(uuid.uuid4())
    evento = {
        "id_evento": id_evento,
        "tipo": "StockBajoUmbral",
        "fecha": "2026-11-18T04:00:00Z",
        "productor": "ms-inventario",
        "id_correlacion": str(uuid.uuid4()),
        "datos": {
            "sku": "PROD-001",
            "id_bodega": 1,
            "saldo": 3.0,
            "stock_minimo": 10.0,
        },
    }

    res = procesar_evento(evento, conexion=db_conn)
    assert res["duplicado"] is False
    assert res["procesado"] is True

    # Verificar alerta_stock
    cursor = db_conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM alerta_stock WHERE sku = %s AND id_bodega = %s", ("PROD-001", 1))
    alerta = cursor.fetchone()
    assert alerta is not None
    assert Decimal(str(alerta["saldo"])) == Decimal("3.000")
    assert Decimal(str(alerta["stock_minimo"])) == Decimal("10.000")
    assert alerta["activa"] == 1

    # Verificar evento_procesado
    cursor.execute("SELECT * FROM evento_procesado WHERE id_evento = %s", (id_evento,))
    ev = cursor.fetchone()
    assert ev is not None
    assert ev["tipo"] == "StockBajoUmbral"
    cursor.close()


def test_movimiento_registrado_entrada_y_salida(db_conn):
    # 1. Entrada por compra
    id_ev_1 = str(uuid.uuid4())
    evento_entrada = {
        "id_evento": id_ev_1,
        "tipo": "MovimientoRegistrado",
        "fecha": "2026-11-18T04:10:00Z",
        "productor": "ms-inventario",
        "id_correlacion": str(uuid.uuid4()),
        "datos": {
            "id_movimiento": 101,
            "sku": "PROD-001",
            "id_bodega": 1,
            "tipo": "ENTRADA_COMPRA",
            "cantidad": 20.0,
            "costo_unitario": 5000.0,
            "saldo_resultante": 20.0,
            "costo_promedio": 5000.0,
            "valor_resultante": 100000.0,
        },
    }
    res_1 = procesar_evento(evento_entrada, conexion=db_conn)
    assert res_1["duplicado"] is False

    cursor = db_conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM saldo_reporte WHERE sku = %s AND id_bodega = %s", ("PROD-001", 1))
    saldo = cursor.fetchone()
    assert saldo is not None
    assert Decimal(str(saldo["cantidad"])) == Decimal("20.000")
    assert Decimal(str(saldo["costo_promedio"])) == Decimal("5000.0000")
    assert Decimal(str(saldo["valor_total"])) == Decimal("100000.00")

    cursor.execute(
        "SELECT * FROM movimiento_diario WHERE sku = %s AND id_bodega = %s AND fecha = %s",
        ("PROD-001", 1, "2026-11-18"),
    )
    mov = cursor.fetchone()
    assert mov is not None
    assert Decimal(str(mov["entradas"])) == Decimal("20.000")
    assert Decimal(str(mov["salidas"])) == Decimal("0.000")

    # 2. Salida
    id_ev_2 = str(uuid.uuid4())
    evento_salida = {
        "id_evento": id_ev_2,
        "tipo": "MovimientoRegistrado",
        "fecha": "2026-11-18T04:20:00Z",
        "productor": "ms-inventario",
        "id_correlacion": str(uuid.uuid4()),
        "datos": {
            "id_movimiento": 102,
            "sku": "PROD-001",
            "id_bodega": 1,
            "tipo": "SALIDA",
            "cantidad": 5.0,
            "costo_unitario": 5000.0,
            "saldo_resultante": 15.0,
            "costo_promedio": 5000.0,
            "valor_resultante": 75000.0,
        },
    }
    res_2 = procesar_evento(evento_salida, conexion=db_conn)
    assert res_2["duplicado"] is False

    cursor.execute("SELECT * FROM saldo_reporte WHERE sku = %s AND id_bodega = %s", ("PROD-001", 1))
    saldo = cursor.fetchone()
    assert Decimal(str(saldo["cantidad"])) == Decimal("15.000")

    cursor.execute(
        "SELECT * FROM movimiento_diario WHERE sku = %s AND id_bodega = %s AND fecha = %s",
        ("PROD-001", 1, "2026-11-18"),
    )
    mov = cursor.fetchone()
    assert Decimal(str(mov["entradas"])) == Decimal("20.000")
    assert Decimal(str(mov["salidas"])) == Decimal("5.000")
    cursor.close()


def test_desactivacion_alerta_stock_tras_reabastecimiento(db_conn):
    cursor = db_conn.cursor()
    # Inserta alerta activa con stock_minimo = 10 y saldo = 2
    cursor.execute(
        "INSERT INTO alerta_stock (sku, id_bodega, saldo, stock_minimo, activa) VALUES (%s, %s, %s, %s, 1)",
        ("PROD-ALERTA", 1, 2.0, 10.0),
    )
    db_conn.commit()
    cursor.close()

    # Movimiento que eleva el saldo_resultante a 15 (> 10)
    evento = {
        "id_evento": str(uuid.uuid4()),
        "tipo": "MovimientoRegistrado",
        "fecha": "2026-11-18T04:30:00Z",
        "productor": "ms-inventario",
        "id_correlacion": str(uuid.uuid4()),
        "datos": {
            "id_movimiento": 103,
            "sku": "PROD-ALERTA",
            "id_bodega": 1,
            "tipo": "ENTRADA_COMPRA",
            "cantidad": 13.0,
            "costo_unitario": 1000.0,
            "saldo_resultante": 15.0,
            "costo_promedio": 1000.0,
            "valor_resultante": 15000.0,
        },
    }
    procesar_evento(evento, conexion=db_conn)

    cursor = db_conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM alerta_stock WHERE sku = %s AND id_bodega = %s", ("PROD-ALERTA", 1))
    alerta = cursor.fetchone()
    assert alerta is not None
    assert Decimal(str(alerta["saldo"])) == Decimal("15.000")
    assert alerta["activa"] == 0  # Se desactivó automáticamente
    cursor.close()


def test_orden_compra_actualizada(db_conn):
    id_evento = str(uuid.uuid4())
    evento = {
        "id_evento": id_evento,
        "tipo": "OrdenCompraActualizada",
        "fecha": "2026-11-18T04:40:00Z",
        "productor": "ms-compras",
        "id_correlacion": str(uuid.uuid4()),
        "datos": {
            "id_orden": 55,
            "numero": "OC-0055",
            "id_proveedor": 7,
            "estado": "APROBADA",
            "total": 350000.50,
        },
    }

    res = procesar_evento(evento, conexion=db_conn)
    assert res["duplicado"] is False

    cursor = db_conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM orden_pendiente WHERE id_orden = %s", (55,))
    orden = cursor.fetchone()
    assert orden is not None
    assert orden["numero"] == "OC-0055"
    assert orden["id_proveedor"] == 7
    assert orden["estado"] == "APROBADA"
    assert Decimal(str(orden["total"])) == Decimal("350000.50")
    cursor.close()


def test_idempotencia_no_repite_modificaciones(db_conn):
    id_evento = str(uuid.uuid4())
    evento = {
        "id_evento": id_evento,
        "tipo": "StockBajoUmbral",
        "fecha": "2026-11-18T04:50:00Z",
        "productor": "ms-inventario",
        "id_correlacion": str(uuid.uuid4()),
        "datos": {
            "sku": "PROD-IDEM",
            "id_bodega": 2,
            "saldo": 1.0,
            "stock_minimo": 5.0,
        },
    }

    # Primera vez: procesado
    res1 = procesar_evento(evento, conexion=db_conn)
    assert res1["duplicado"] is False

    # Segunda vez: detectado como duplicado
    res2 = procesar_evento(evento, conexion=db_conn)
    assert res2["duplicado"] is True


def test_evento_incompleto_lanza_error():
    evento_corrupto = {
        "id_evento": str(uuid.uuid4()),
        "tipo": "MovimientoRegistrado",
        "datos": {
            "id_movimiento": 999,
            "tipo": "TIPO_INVALIDO",
            # faltan sku, id_bodega, cantidad, etc.
        },
    }
    with pytest.raises(ValueError) as exc:
        procesar_evento(evento_corrupto)
    assert "incompleto" in str(exc.value)


def test_consumidor_ack_en_exito(db_conn):
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1234

    id_evento = str(uuid.uuid4())
    body = json.dumps({
        "id_evento": id_evento,
        "tipo": "StockBajoUmbral",
        "fecha": "2026-11-18T05:00:00Z",
        "productor": "ms-inventario",
        "id_correlacion": str(uuid.uuid4()),
        "datos": {
            "sku": "PROD-ACK",
            "id_bodega": 1,
            "saldo": 2.0,
            "stock_minimo": 8.0,
        },
    }).encode("utf-8")

    procesar_mensaje_amqp(mock_ch, mock_method, None, body)

    # Debe hacer ack
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=1234)
    mock_ch.basic_nack.assert_not_called()


def test_consumidor_nack_en_json_corrupto():
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 5678

    body = b"esto no es un json valido"

    procesar_mensaje_amqp(mock_ch, mock_method, None, body)

    # Debe hacer reject con requeue=True
    mock_ch.basic_reject.assert_called_once_with(delivery_tag=5678, requeue=True)
    mock_ch.basic_ack.assert_not_called()
