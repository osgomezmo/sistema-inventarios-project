"""Consultas de traslados (D46). Todo parametrizado con %s."""

COLUMNAS = (
    "id_traslado, sku, id_bodega_origen, id_bodega_destino, cantidad, motivo,"
    " id_usuario, fecha"
)
ORDEN_RECIENTES = "ORDER BY fecha DESC, id_traslado DESC"


def insertar(cursor, sku, id_bodega_origen, id_bodega_destino, cantidad, motivo, id_usuario):
    """Inserta el traslado con fecha = UTC_TIMESTAMP() y devuelve su id."""
    cursor.execute(
        "INSERT INTO traslados (sku, id_bodega_origen, id_bodega_destino, cantidad, motivo,"
        " id_usuario, fecha) VALUES (%s, %s, %s, %s, %s, %s, UTC_TIMESTAMP())",
        (sku, id_bodega_origen, id_bodega_destino, cantidad, motivo, id_usuario),
    )
    return cursor.lastrowid


def _con_movimientos(cursor, traslados):
    """Agrega {salida, entrada} a cada traslado con una sola consulta (sin N+1)."""
    if not traslados:
        return traslados
    ids = [t["id_traslado"] for t in traslados]
    marcadores = ", ".join(["%s"] * len(ids))
    cursor.execute(
        "SELECT id_traslado, id_movimiento, tipo FROM movimientos"
        f" WHERE id_traslado IN ({marcadores})",
        ids,
    )
    por_traslado = {i: {"salida": None, "entrada": None} for i in ids}
    for fila in cursor.fetchall():
        clave = "salida" if fila["tipo"] == "TRASLADO_SALIDA" else "entrada"
        por_traslado[fila["id_traslado"]][clave] = fila["id_movimiento"]
    for traslado in traslados:
        traslado["movimientos"] = por_traslado[traslado["id_traslado"]]
    return traslados


def obtener(cursor, id_traslado):
    cursor.execute(f"SELECT {COLUMNAS} FROM traslados WHERE id_traslado = %s", (id_traslado,))
    fila = cursor.fetchone()
    return _con_movimientos(cursor, [fila])[0] if fila else None


def listar(cursor, limite, offset, sku=None, desde=None, hasta=None):
    """Página de traslados, del más reciente al más antiguo, y el total."""
    condiciones, parametros = [], []
    if sku is not None:
        condiciones.append("sku = %s")
        parametros.append(sku)
    if desde is not None:
        condiciones.append("fecha >= %s")
        parametros.append(desde[0])
    if hasta is not None:
        condiciones.append("fecha <= %s" if hasta[1] else "fecha < %s")
        parametros.append(hasta[0])
    donde = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""

    cursor.execute(f"SELECT COUNT(*) AS total FROM traslados {donde}", parametros)
    total = cursor.fetchone()["total"]
    cursor.execute(
        f"SELECT {COLUMNAS} FROM traslados {donde} {ORDEN_RECIENTES} LIMIT %s OFFSET %s",
        [*parametros, limite, offset],
    )
    return _con_movimientos(cursor, cursor.fetchall()), total
