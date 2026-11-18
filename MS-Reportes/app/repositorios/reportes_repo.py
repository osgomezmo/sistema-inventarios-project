"""Consultas SQL agregadas y analíticas para reportes y dashboard.

Todas las consultas están parametrizadas con %s y no usan ORM.
"""

from decimal import Decimal


def obtener_valorizacion_por_producto(cursor, id_bodega=None):
    """Devuelve saldos agrupados por producto y bodega."""
    params = (id_bodega, id_bodega)
    sql = """
        SELECT
            sr.sku,
            sr.id_bodega,
            sr.cantidad,
            sr.costo_promedio,
            sr.valor_total,
            sr.actualizado_en
        FROM saldo_reporte sr
        WHERE (%s IS NULL OR sr.id_bodega = %s)
        ORDER BY sr.valor_total DESC, sr.sku ASC
    """
    cursor.execute(sql, params)
    return cursor.fetchall()


def obtener_valorizacion_por_bodega(cursor, id_bodega=None):
    """Devuelve saldos agrupados por bodega."""
    params = (id_bodega, id_bodega)
    sql = """
        SELECT
            sr.id_bodega,
            COUNT(DISTINCT sr.sku) AS total_productos,
            COALESCE(SUM(sr.cantidad), 0) AS cantidad_total,
            COALESCE(SUM(sr.valor_total), 0) AS valor_total
        FROM saldo_reporte sr
        WHERE (%s IS NULL OR sr.id_bodega = %s)
        GROUP BY sr.id_bodega
        ORDER BY sr.id_bodega ASC
    """
    cursor.execute(sql, params)
    return cursor.fetchall()


def obtener_totales_valorizacion(cursor, id_bodega=None):
    """Devuelve los totales generales de inventario."""
    params = (id_bodega, id_bodega)
    sql = """
        SELECT
            COALESCE(SUM(sr.cantidad), 0) AS cantidad_total,
            COALESCE(SUM(sr.valor_total), 0) AS valor_total
        FROM saldo_reporte sr
        WHERE (%s IS NULL OR sr.id_bodega = %s)
    """
    cursor.execute(sql, params)
    fila = cursor.fetchone()
    if not fila:
        return {"cantidad_total": Decimal("0.000"), "valor_total": Decimal("0.00")}
    return fila


def obtener_rotacion(cursor, desde=None, hasta=None, id_bodega=None):
    """Devuelve rotación de productos agrupada por SKU."""
    params = (desde, desde, hasta, hasta, id_bodega, id_bodega)
    sql = """
        SELECT
            md.sku,
            COALESCE(SUM(md.entradas), 0) AS total_entradas,
            COALESCE(SUM(md.salidas), 0) AS total_salidas
        FROM movimiento_diario md
        WHERE (%s IS NULL OR md.fecha >= %s)
          AND (%s IS NULL OR md.fecha <= %s)
          AND (%s IS NULL OR md.id_bodega = %s)
        GROUP BY md.sku
    """
    cursor.execute(sql, params)
    return cursor.fetchall()


def obtener_alertas_stock_bajo(cursor, id_bodega=None):
    """Devuelve las alertas de stock bajo activas."""
    params = (id_bodega, id_bodega)
    sql = """
        SELECT
            a.sku,
            a.id_bodega,
            a.saldo,
            a.stock_minimo,
            (a.saldo - a.stock_minimo) AS diferencia,
            a.fecha,
            a.activa
        FROM alerta_stock a
        WHERE a.activa = 1
          AND (%s IS NULL OR a.id_bodega = %s)
        ORDER BY (a.saldo - a.stock_minimo) ASC, a.fecha DESC
    """
    cursor.execute(sql, params)
    return cursor.fetchall()


def obtener_metricas_dashboard(cursor):
    """Calcula las 5 métricas canónicas del dashboard consolidado."""
    # 1. Valor total inventario
    cursor.execute("SELECT COALESCE(SUM(valor_total), 0) AS total FROM saldo_reporte")
    fila_valor = cursor.fetchone()
    valor_total = float(fila_valor["total"]) if fila_valor else 0.0

    # 2. Productos en stock bajo (activos)
    cursor.execute("SELECT COUNT(DISTINCT sku) AS total FROM alerta_stock WHERE activa = 1")
    fila_stock = cursor.fetchone()
    productos_stock_bajo = int(fila_stock["total"]) if fila_stock else 0

    # 3. Órdenes pendientes
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM orden_pendiente
        WHERE estado IN ('BORRADOR', 'APROBADA', 'PENDIENTE', 'RECIBIDA_PARCIAL')
        """
    )
    fila_ordenes = cursor.fetchone()
    ordenes_pendientes = int(fila_ordenes["total"]) if fila_ordenes else 0

    # 4. Mayor y menor rotación (Top 5)
    cursor.execute(
        """
        SELECT
            sku,
            COALESCE(SUM(entradas), 0) AS total_entradas,
            COALESCE(SUM(salidas), 0) AS total_salidas
        FROM movimiento_diario
        GROUP BY sku
        ORDER BY total_salidas DESC, total_entradas DESC
        LIMIT 5
        """
    )
    mayor_rotacion = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            sku,
            COALESCE(SUM(entradas), 0) AS total_entradas,
            COALESCE(SUM(salidas), 0) AS total_salidas
        FROM movimiento_diario
        GROUP BY sku
        ORDER BY total_salidas ASC, total_entradas ASC
        LIMIT 5
        """
    )
    menor_rotacion = cursor.fetchall()

    return {
        "valor_total_inventario": valor_total,
        "productos_stock_bajo": productos_stock_bajo,
        "ordenes_pendientes": ordenes_pendientes,
        "mayor_rotacion": mayor_rotacion,
        "menor_rotacion": menor_rotacion,
    }
