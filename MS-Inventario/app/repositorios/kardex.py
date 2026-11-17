"""Consultas del kardex (D45). Solo lectura sobre movimientos, con el índice
(sku, id_bodega, fecha, id_movimiento). Todo parametrizado con %s."""

from app.repositorios.movimientos import COLUMNAS_LECTURA


def saldo_anterior(cursor, sku, id_bodega, inicio):
    """Último movimiento antes de `inicio`: su saldo y valor resultantes, o None."""
    cursor.execute(
        "SELECT saldo_resultante, valor_resultante FROM movimientos"
        " WHERE sku = %s AND id_bodega = %s AND fecha < %s"
        " ORDER BY fecha DESC, id_movimiento DESC LIMIT 1",
        (sku, id_bodega, inicio),
    )
    return cursor.fetchone()


def movimientos_en_rango(cursor, sku, id_bodega, inicio, fin, fin_inclusivo, limite):
    """Movimientos del rango en orden cronológico; trae hasta `limite` filas."""
    comparacion = "<=" if fin_inclusivo else "<"
    cursor.execute(
        f"SELECT {COLUMNAS_LECTURA} FROM movimientos"
        f" WHERE sku = %s AND id_bodega = %s AND fecha >= %s AND fecha {comparacion} %s"
        " ORDER BY fecha ASC, id_movimiento ASC LIMIT %s",
        (sku, id_bodega, inicio, fin, limite),
    )
    return cursor.fetchall()
