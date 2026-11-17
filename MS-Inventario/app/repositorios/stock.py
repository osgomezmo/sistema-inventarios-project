"""Consultas de saldos. Todas reciben un cursor de diccionarios y usan
parámetros %s; los fragmentos de SQL que se combinan son constantes."""

# valor y bajo_minimo se calculan en SQL (D38).
VALOR = "ROUND(cantidad * costo_promedio, 2)"
BAJO_MINIMO = "cantidad <= stock_minimo"
COLUMNAS_LISTADO = (
    f"sku, id_bodega, cantidad, costo_promedio, {VALOR} AS valor, stock_minimo,"
    f" ({BAJO_MINIMO}) AS bajo_minimo"
)
COLUMNAS_SKU = f"sku, id_bodega, cantidad, costo_promedio, {VALOR} AS valor"


def _donde(sku=None, id_bodega=None, bajo_minimo=None):
    """Arma el WHERE común del conteo y del listado: (sql, parámetros)."""
    condiciones, parametros = [], []
    if sku is not None:
        # La intercalación de la columna no distingue mayúsculas.
        condiciones.append("sku = %s")
        parametros.append(sku)
    if id_bodega is not None:
        condiciones.append("id_bodega = %s")
        parametros.append(id_bodega)
    if bajo_minimo is True:
        condiciones.append(BAJO_MINIMO)
    elif bajo_minimo is False:
        condiciones.append(f"NOT ({BAJO_MINIMO})")
    sql = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    return sql, parametros


def listar(cursor, limite, offset, **filtros):
    """Página de saldos ordenada por sku e id_bodega, y el total que cumple los filtros."""
    donde, parametros = _donde(**filtros)
    cursor.execute(f"SELECT COUNT(*) AS total FROM saldos {donde}", parametros)
    total = cursor.fetchone()["total"]
    cursor.execute(
        f"SELECT {COLUMNAS_LISTADO} FROM saldos {donde}"
        " ORDER BY sku, id_bodega LIMIT %s OFFSET %s",
        [*parametros, limite, offset],
    )
    filas = cursor.fetchall()
    for fila in filas:
        # MySQL devuelve la comparación como 0 o 1.
        fila["bajo_minimo"] = bool(fila["bajo_minimo"])
    return filas, total


def saldos_de_sku(cursor, sku):
    """Saldos de un SKU en todas las bodegas, ordenados por id_bodega."""
    cursor.execute(
        f"SELECT {COLUMNAS_SKU} FROM saldos WHERE sku = %s ORDER BY id_bodega", (sku,)
    )
    return cursor.fetchall()
