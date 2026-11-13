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


def obtener_bloqueando(cursor, id_categoria):
    """Como `obtener`, pero bloquea la fila hasta el fin de la transacción."""
    cursor.execute(
        f"SELECT {COLUMNAS} FROM categorias WHERE id_categoria = %s FOR UPDATE",
        (id_categoria,),
    )
    return cursor.fetchone()


def nombre_repetido(cursor, nombre, id_padre, excluir_id=None):
    """True si ya hay otra categoría con ese nombre en el mismo nivel.

    La comparación usa la intercalación de la columna (utf8mb4_0900_ai_ci), así
    que no distingue mayúsculas ni tildes. FOR UPDATE bloquea también el rango
    revisado, para que otra transacción no cree el mismo nombre a la vez.
    """
    condiciones, parametros = ["nombre = %s"], [nombre]
    if id_padre is None:
        condiciones.append("id_categoria_padre IS NULL")
    else:
        condiciones.append("id_categoria_padre = %s")
        parametros.append(id_padre)
    if excluir_id is not None:
        condiciones.append("id_categoria <> %s")
        parametros.append(excluir_id)

    donde = " AND ".join(condiciones)
    cursor.execute(f"SELECT id_categoria FROM categorias WHERE {donde} LIMIT 1 FOR UPDATE", parametros)
    return cursor.fetchone() is not None


def contar_subcategorias(cursor, id_categoria):
    cursor.execute(
        "SELECT COUNT(*) AS total FROM categorias WHERE id_categoria_padre = %s",
        (id_categoria,),
    )
    return cursor.fetchone()["total"]


def insertar(cursor, nombre, descripcion, id_padre):
    cursor.execute(
        "INSERT INTO categorias (nombre, descripcion, id_categoria_padre) VALUES (%s, %s, %s)",
        (nombre, descripcion, id_padre),
    )
    return cursor.lastrowid


def actualizar(cursor, id_categoria, nombre, descripcion, id_padre):
    """Reemplaza nombre, descripción y padre. El estado no se toca."""
    cursor.execute(
        "UPDATE categorias SET nombre = %s, descripcion = %s, id_categoria_padre = %s"
        " WHERE id_categoria = %s",
        (nombre, descripcion, id_padre, id_categoria),
    )


def _marcadores(ids):
    """Un %s por id, para usar en IN (...); los valores van como parámetros."""
    return ", ".join(["%s"] * len(ids))


def bloquear_subcategorias(cursor, id_padre):
    """Subcategorías de `id_padre`, bloqueadas hasta el fin de la transacción."""
    cursor.execute(
        f"SELECT {COLUMNAS} FROM categorias WHERE id_categoria_padre = %s"
        f" {ORDEN} FOR UPDATE",
        (id_padre,),
    )
    return cursor.fetchall()


def contar_productos_activos(cursor, ids_categoria):
    """Productos ACTIVOS de cualquiera de las categorías indicadas.

    Es una lectura con bloqueo (FOR SHARE): ve lo último confirmado y no la
    instantánea de la transacción.
    """
    ids = list(ids_categoria)
    if not ids:
        return 0
    cursor.execute(
        "SELECT COUNT(*) AS total FROM productos"
        f" WHERE estado = %s AND id_categoria IN ({_marcadores(ids)}) FOR SHARE",
        ["ACTIVO", *ids],
    )
    return cursor.fetchone()["total"]


def actualizar_estado(cursor, ids_categoria, estado):
    ids = list(ids_categoria)
    if not ids:
        return
    cursor.execute(
        f"UPDATE categorias SET estado = %s WHERE id_categoria IN ({_marcadores(ids)})",
        [estado, *ids],
    )
