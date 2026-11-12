"""Consultas de categorías. Todas reciben un cursor de diccionarios y usan
parámetros %s; los fragmentos de SQL que se combinan son constantes."""

COLUMNAS = "id_categoria, nombre, descripcion, id_categoria_padre, estado"
ORDEN = "ORDER BY nombre, id_categoria"


def _filtro(condiciones, parametros, estado):
    if estado is not None:
        condiciones.append("estado = %s")
        parametros.append(estado)
    return " AND ".join(condiciones)


def _pagina(cursor, condiciones, parametros, limite, offset):
    donde = " AND ".join(condiciones)
    cursor.execute(f"SELECT COUNT(*) AS total FROM categorias WHERE {donde}", parametros)
    total = cursor.fetchone()["total"]
    cursor.execute(
        f"SELECT {COLUMNAS} FROM categorias WHERE {donde} {ORDEN} LIMIT %s OFFSET %s",
        [*parametros, limite, offset],
    )
    return cursor.fetchall(), total


def listar_raices(cursor, estado, limite, offset):
    """Página de categorías raíz y el total que cumple el filtro."""
    condiciones, parametros = ["id_categoria_padre IS NULL"], []
    _filtro(condiciones, parametros, estado)
    return _pagina(cursor, condiciones, parametros, limite, offset)


def listar_hijas(cursor, id_padre, estado, limite, offset):
    """Página plana de las subcategorías de `id_padre`."""
    condiciones, parametros = ["id_categoria_padre = %s"], [id_padre]
    _filtro(condiciones, parametros, estado)
    return _pagina(cursor, condiciones, parametros, limite, offset)


def subcategorias_por_padre(cursor, ids_padre, estado=None):
    """Subcategorías de varios padres en una sola consulta: {id_padre: [filas]}."""
    agrupadas = {id_padre: [] for id_padre in ids_padre}
    if not agrupadas:
        return agrupadas

    marcadores = ", ".join(["%s"] * len(agrupadas))
    condiciones = [f"id_categoria_padre IN ({marcadores})"]
    parametros = list(agrupadas)
    donde = _filtro(condiciones, parametros, estado)
    cursor.execute(f"SELECT {COLUMNAS} FROM categorias WHERE {donde} {ORDEN}", parametros)
    for fila in cursor.fetchall():
        agrupadas[fila["id_categoria_padre"]].append(fila)
    return agrupadas


def obtener(cursor, id_categoria):
    cursor.execute(f"SELECT {COLUMNAS} FROM categorias WHERE id_categoria = %s", (id_categoria,))
    return cursor.fetchone()
