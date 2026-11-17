"""Kardex. La tabla movimientos es inmutable: aquí solo se inserta y se lee;
nunca hay UPDATE ni DELETE sobre ella (D35, D41)."""

COLUMNAS_INSERTAR = (
    "sku", "id_bodega", "tipo", "cantidad", "costo_unitario", "saldo_resultante",
    "costo_promedio", "valor_resultante", "motivo", "documento_referencia", "id_usuario",
    "id_traslado",
)


def insertar_movimiento(cursor, **campos):
    """Inserta la fila con fecha = UTC_TIMESTAMP() y devuelve (id, fecha).

    La fecha se lee de vuelta en la misma transacción, ya con el saldo bloqueado.
    """
    columnas = ", ".join(COLUMNAS_INSERTAR)
    marcadores = ", ".join(["%s"] * len(COLUMNAS_INSERTAR))
    cursor.execute(
        f"INSERT INTO movimientos ({columnas}, fecha) VALUES ({marcadores}, UTC_TIMESTAMP())",
        [campos[c] for c in COLUMNAS_INSERTAR],
    )
    id_movimiento = cursor.lastrowid
    cursor.execute("SELECT fecha FROM movimientos WHERE id_movimiento = %s", (id_movimiento,))
    return id_movimiento, cursor.fetchone()["fecha"]


# Campos públicos de un movimiento (D43): id_traslado es interno y no se expone.
COLUMNAS_LECTURA = (
    "id_movimiento, sku, id_bodega, tipo, cantidad, costo_unitario, saldo_resultante,"
    " costo_promedio, valor_resultante, motivo, documento_referencia, id_usuario, fecha"
)
ORDEN_RECIENTES = "ORDER BY fecha DESC, id_movimiento DESC"


def _donde(sku=None, id_bodega=None, tipo=None, desde=None, hasta=None):
    """WHERE común del conteo y del listado. desde y hasta son (instante, inclusivo)."""
    condiciones, parametros = [], []
    for columna, valor in (("sku", sku), ("id_bodega", id_bodega), ("tipo", tipo)):
        if valor is not None:
            condiciones.append(f"{columna} = %s")
            parametros.append(valor)
    if desde is not None:
        condiciones.append("fecha >= %s")
        parametros.append(desde[0])
    if hasta is not None:
        instante, inclusivo = hasta
        condiciones.append("fecha <= %s" if inclusivo else "fecha < %s")
        parametros.append(instante)
    sql = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    return sql, parametros


def listar(cursor, limite, offset, **filtros):
    """Página de movimientos, del más reciente al más antiguo, y el total."""
    donde, parametros = _donde(**filtros)
    cursor.execute(f"SELECT COUNT(*) AS total FROM movimientos {donde}", parametros)
    total = cursor.fetchone()["total"]
    cursor.execute(
        f"SELECT {COLUMNAS_LECTURA} FROM movimientos {donde} {ORDEN_RECIENTES}"
        " LIMIT %s OFFSET %s",
        [*parametros, limite, offset],
    )
    return cursor.fetchall(), total


def obtener(cursor, id_movimiento):
    cursor.execute(
        f"SELECT {COLUMNAS_LECTURA} FROM movimientos WHERE id_movimiento = %s", (id_movimiento,)
    )
    return cursor.fetchone()
