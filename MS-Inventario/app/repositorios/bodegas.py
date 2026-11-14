"""Consultas de bodegas. Todas reciben un cursor de diccionarios y usan
parámetros %s; los fragmentos de SQL que se combinan son constantes."""

COLUMNAS = "id_bodega, codigo, nombre, direccion, estado"
ORDEN = "ORDER BY nombre, id_bodega"


def listar(cursor, estado, limite, offset):
    """Página de bodegas y el total que cumple el filtro."""
    condiciones, parametros = [], []
    if estado is not None:
        condiciones.append("estado = %s")
        parametros.append(estado)
    donde = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""

    cursor.execute(f"SELECT COUNT(*) AS total FROM bodegas {donde}", parametros)
    total = cursor.fetchone()["total"]
    cursor.execute(
        f"SELECT {COLUMNAS} FROM bodegas {donde} {ORDEN} LIMIT %s OFFSET %s",
        [*parametros, limite, offset],
    )
    return cursor.fetchall(), total


def obtener(cursor, id_bodega):
    cursor.execute(f"SELECT {COLUMNAS} FROM bodegas WHERE id_bodega = %s", (id_bodega,))
    return cursor.fetchone()


def obtener_bloqueando(cursor, id_bodega):
    """Como `obtener`, pero bloquea la fila hasta el fin de la transacción."""
    cursor.execute(
        f"SELECT {COLUMNAS} FROM bodegas WHERE id_bodega = %s FOR UPDATE", (id_bodega,)
    )
    return cursor.fetchone()


def insertar(cursor, codigo, nombre, direccion):
    """Inserta una bodega ACTIVA y devuelve su id. Un código repetido lanza
    IntegrityError (errno 1062) por el índice único."""
    cursor.execute(
        "INSERT INTO bodegas (codigo, nombre, direccion) VALUES (%s, %s, %s)",
        (codigo, nombre, direccion),
    )
    return cursor.lastrowid


def actualizar(cursor, id_bodega, nombre, direccion):
    """Reemplaza nombre y dirección. El código y el estado no se tocan."""
    cursor.execute(
        "UPDATE bodegas SET nombre = %s, direccion = %s WHERE id_bodega = %s",
        (nombre, direccion, id_bodega),
    )
