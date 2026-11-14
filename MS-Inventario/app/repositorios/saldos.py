"""Consultas de escritura sobre saldos para el motor de movimientos (D41).

Todas reciben el cursor de una transacción abierta por quien llama y usan
parámetros %s; los fragmentos de SQL que se combinan son constantes.
"""

COLUMNAS = "id_saldo, sku, id_bodega, cantidad, costo_promedio, stock_minimo"


def leer_bodega_compartida(cursor, id_bodega):
    """Lee la bodega con bloqueo compartido (FOR SHARE): nadie puede
    inactivarla mientras dura el movimiento (D36)."""
    cursor.execute(
        "SELECT id_bodega, estado FROM bodegas WHERE id_bodega = %s FOR SHARE", (id_bodega,)
    )
    return cursor.fetchone()


def asegurar_saldo(cursor, sku, id_bodega, stock_minimo):
    """Crea el saldo en cero si no existe; si existe, no lo cambia."""
    cursor.execute(
        "INSERT INTO saldos (sku, id_bodega, cantidad, costo_promedio, stock_minimo)"
        " VALUES (%s, %s, 0, 0, %s)"
        " ON DUPLICATE KEY UPDATE id_saldo = id_saldo",
        (sku, id_bodega, stock_minimo),
    )


def bloquear_saldo(cursor, sku, id_bodega):
    """Lee el saldo con FOR UPDATE; None si no existe."""
    cursor.execute(
        f"SELECT {COLUMNAS} FROM saldos WHERE sku = %s AND id_bodega = %s FOR UPDATE",
        (sku, id_bodega),
    )
    return cursor.fetchone()


def actualizar_saldo(cursor, id_saldo, cantidad, costo_promedio, stock_minimo):
    """Fija el saldo nuevo. actualizado_en se fija a mano: MySQL no admite
    ON UPDATE con UTC_TIMESTAMP (D35)."""
    cursor.execute(
        "UPDATE saldos SET cantidad = %s, costo_promedio = %s, stock_minimo = %s,"
        " actualizado_en = UTC_TIMESTAMP() WHERE id_saldo = %s",
        (cantidad, costo_promedio, stock_minimo, id_saldo),
    )
