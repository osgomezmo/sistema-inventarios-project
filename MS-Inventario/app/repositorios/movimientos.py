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
