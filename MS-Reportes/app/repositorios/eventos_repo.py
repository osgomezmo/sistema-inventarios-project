"""Repositorio de eventos y proyecciones para MS-Reportes.

Procesa en una única transacción de MySQL cada evento consumido de RabbitMQ:
  - MovimientoRegistrado -> saldo_reporte, movimiento_diario, alerta_stock
  - OrdenCompraActualizada -> orden_pendiente
  - StockBajoUmbral -> alerta_stock
  - evento_procesado -> idempotencia
"""

from datetime import datetime, timezone
from decimal import Decimal

from app.db import abrir_conexion

TIPOS_ENTRADA = {
    "ENTRADA_COMPRA",
    "AJUSTE_POSITIVO",
    "TRASLADO_ENTRADA",
    "DEVOLUCION_CLIENTE",
}

TIPOS_SALIDA = {
    "SALIDA",
    "AJUSTE_NEGATIVO",
    "TRASLADO_SALIDA",
    "DEVOLUCION_PROVEEDOR",
}


def _extraer_fecha(fecha_raw):
    """Extrae la fecha en formato YYYY-MM-DD desde una cadena ISO 8601 o fecha UTC actual."""
    if isinstance(fecha_raw, str) and len(fecha_raw) >= 10:
        posible_fecha = fecha_raw[:10]
        try:
            datetime.strptime(posible_fecha, "%Y-%m-%d")
            return posible_fecha
        except ValueError:
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _procesar_movimiento_registrado(cursor, evento, datos):
    """Aplica las proyecciones asociadas al evento MovimientoRegistrado."""
    campos_requeridos = [
        "sku",
        "id_bodega",
        "tipo",
        "cantidad",
        "costo_unitario",
        "saldo_resultante",
        "costo_promedio",
        "valor_resultante",
    ]
    for campo in campos_requeridos:
        if campo not in datos or datos[campo] is None:
            raise ValueError(f"MovimientoRegistrado incompleto: falta '{campo}'.")

    sku = str(datos["sku"]).strip()
    if not sku:
        raise ValueError("MovimientoRegistrado: 'sku' no puede estar vacío.")

    id_bodega = int(datos["id_bodega"])
    tipo_mov = str(datos["tipo"]).strip().upper()
    cantidad = Decimal(str(datos["cantidad"]))
    costo_unitario = Decimal(str(datos["costo_unitario"]))
    saldo_resultante = Decimal(str(datos["saldo_resultante"]))
    costo_promedio = Decimal(str(datos["costo_promedio"]))
    valor_resultante = Decimal(str(datos["valor_resultante"]))

    # 1. Actualizar saldo_reporte con INSERT ... ON DUPLICATE KEY UPDATE
    cursor.execute(
        """
        INSERT INTO saldo_reporte (sku, id_bodega, cantidad, costo_promedio, valor_total, actualizado_en)
        VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP())
        ON DUPLICATE KEY UPDATE
            cantidad = VALUES(cantidad),
            costo_promedio = VALUES(costo_promedio),
            valor_total = VALUES(valor_total),
            actualizado_en = UTC_TIMESTAMP()
        """,
        (sku, id_bodega, saldo_resultante, costo_promedio, valor_resultante),
    )

    # 2. Actualizar movimiento_diario clasificando el tipo
    fecha_mov = _extraer_fecha(evento.get("fecha"))
    if tipo_mov in TIPOS_ENTRADA:
        cursor.execute(
            """
            INSERT INTO movimiento_diario (sku, id_bodega, fecha, entradas, salidas)
            VALUES (%s, %s, %s, %s, 0.000)
            ON DUPLICATE KEY UPDATE
                entradas = entradas + VALUES(entradas)
            """,
            (sku, id_bodega, fecha_mov, cantidad),
        )
    elif tipo_mov in TIPOS_SALIDA:
        cursor.execute(
            """
            INSERT INTO movimiento_diario (sku, id_bodega, fecha, entradas, salidas)
            VALUES (%s, %s, %s, 0.000, %s)
            ON DUPLICATE KEY UPDATE
                salidas = salidas + VALUES(salidas)
            """,
            (sku, id_bodega, fecha_mov, cantidad),
        )
    else:
        # Si el tipo no está categorizado explícitamente, se registra como salida o se lanza error
        raise ValueError(f"MovimientoRegistrado: tipo '{tipo_mov}' no reconocido.")

    # 3. Si existe registro en alerta_stock para (sku, id_bodega), actualiza saldo y desactiva si supera mínimo
    cursor.execute(
        """
        UPDATE alerta_stock
        SET saldo = %s,
            activa = CASE WHEN %s > stock_minimo THEN 0 ELSE activa END
        WHERE sku = %s AND id_bodega = %s
        """,
        (saldo_resultante, saldo_resultante, sku, id_bodega),
    )


def _procesar_orden_compra_actualizada(cursor, datos):
    """Aplica las proyecciones asociadas al evento OrdenCompraActualizada."""
    campos_requeridos = ["id_orden", "id_proveedor", "estado"]
    for campo in campos_requeridos:
        if campo not in datos or datos[campo] is None:
            raise ValueError(f"OrdenCompraActualizada incompleta: falta '{campo}'.")

    id_orden = int(datos["id_orden"])
    id_proveedor = int(datos["id_proveedor"])
    estado = str(datos["estado"]).strip().upper()
    if not estado:
        raise ValueError("OrdenCompraActualizada: 'estado' no puede estar vacío.")

    numero = str(datos["numero"]).strip() if datos.get("numero") is not None else None
    total = Decimal(str(datos.get("total", "0.00")))

    cursor.execute(
        """
        INSERT INTO orden_pendiente (id_orden, numero, id_proveedor, estado, total, actualizada_en)
        VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP())
        ON DUPLICATE KEY UPDATE
            numero = COALESCE(VALUES(numero), numero),
            id_proveedor = VALUES(id_proveedor),
            estado = VALUES(estado),
            total = VALUES(total),
            actualizada_en = UTC_TIMESTAMP()
        """,
        (id_orden, numero, id_proveedor, estado, total),
    )


def _procesar_stock_bajo_umbral(cursor, datos):
    """Aplica las proyecciones asociadas al evento StockBajoUmbral."""
    campos_requeridos = ["sku", "id_bodega", "saldo", "stock_minimo"]
    for campo in campos_requeridos:
        if campo not in datos or datos[campo] is None:
            raise ValueError(f"StockBajoUmbral incompleto: falta '{campo}'.")

    sku = str(datos["sku"]).strip()
    if not sku:
        raise ValueError("StockBajoUmbral: 'sku' no puede estar vacío.")

    id_bodega = int(datos["id_bodega"])
    saldo = Decimal(str(datos["saldo"]))
    stock_minimo = Decimal(str(datos["stock_minimo"]))

    cursor.execute(
        """
        INSERT INTO alerta_stock (sku, id_bodega, saldo, stock_minimo, activa, fecha)
        VALUES (%s, %s, %s, %s, 1, UTC_TIMESTAMP())
        ON DUPLICATE KEY UPDATE
            saldo = VALUES(saldo),
            stock_minimo = VALUES(stock_minimo),
            activa = 1,
            fecha = UTC_TIMESTAMP()
        """,
        (sku, id_bodega, saldo, stock_minimo),
    )


def procesar_evento(evento, conexion=None, config=None):
    """Procesa un evento en una única transacción de MySQL.

    Retorna un diccionario indicando si fue procesado o si era duplicado.
    Lanza excepción si faltan campos o si ocurre un fallo en base de datos.
    """
    if not isinstance(evento, dict):
        raise ValueError("El evento debe ser un objeto JSON (dict).")

    id_evento = str(evento.get("id_evento", "")).strip()
    tipo = str(evento.get("tipo", "")).strip()
    datos = evento.get("datos")

    if not id_evento:
        raise ValueError("id_evento es obligatorio.")
    if not tipo:
        raise ValueError("tipo es obligatorio.")
    if not isinstance(datos, dict):
        raise ValueError("datos debe ser un diccionario.")

    conn = conexion if conexion is not None else abrir_conexion(config)
    debe_cerrar = conexion is None
    cursor = conn.cursor(dictionary=True)

    try:
        if not getattr(conn, "in_transaction", False):
            conn.start_transaction()

        # 1. Verificar idempotencia
        cursor.execute("SELECT 1 FROM evento_procesado WHERE id_evento = %s", (id_evento,))
        if cursor.fetchone():
            try:
                conn.rollback()
            except Exception:
                pass
            return {"duplicado": True, "id_evento": id_evento}

        # 2. Ejecutar según tipo
        if tipo == "MovimientoRegistrado":
            _procesar_movimiento_registrado(cursor, evento, datos)
        elif tipo == "OrdenCompraActualizada":
            _procesar_orden_compra_actualizada(cursor, datos)
        elif tipo == "StockBajoUmbral":
            _procesar_stock_bajo_umbral(cursor, datos)
        else:
            raise ValueError(f"Tipo de evento no soportado por MS-Reportes: {tipo}")

        # 3. Registrar evento procesado
        cursor.execute(
            "INSERT INTO evento_procesado (id_evento, tipo, procesado_en) VALUES (%s, %s, UTC_TIMESTAMP())",
            (id_evento, tipo),
        )

        conn.commit()
        return {"duplicado": False, "procesado": True, "tipo": tipo, "id_evento": id_evento}

    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        cursor.close()
        if debe_cerrar:
            conn.close()
