"""Consultas de productos. Todas reciben un cursor de diccionarios y usan
parámetros %s; los fragmentos de SQL que se combinan son constantes."""

COLUMNAS = (
    "id_producto, sku, nombre, descripcion, marca, id_categoria,"
    " unidad_medida, precio_venta, stock_minimo, estado"
)
COLUMNAS_SKU = "sku, nombre, estado, unidad_medida, stock_minimo, id_categoria"
ORDEN = "ORDER BY nombre, id_producto"


def escapar_like(texto):
    """Escapa \\, % y _ para que valgan literalmente dentro de un LIKE."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _marcadores(valores):
    return ", ".join(["%s"] * len(valores))


def _donde(q=None, id_categoria=None, estado=None, precio_min=None, precio_max=None,
           skus=None):
    """Arma el WHERE común del conteo y del listado: (sql, parámetros)."""
    condiciones, parametros = [], []

    if q:
        patron = f"%{escapar_like(q)}%"
        condiciones.append("(sku LIKE %s ESCAPE '\\\\' OR nombre LIKE %s ESCAPE '\\\\')")
        parametros += [patron, patron]
    if id_categoria is not None:
        # Una raíz incluye los productos de sus subcategorías.
        condiciones.append(
            "(id_categoria = %s OR id_categoria IN"
            " (SELECT id_categoria FROM categorias WHERE id_categoria_padre = %s))"
        )
        parametros += [id_categoria, id_categoria]
    if estado is not None:
        condiciones.append("estado = %s")
        parametros.append(estado)
    if precio_min is not None:
        condiciones.append("precio_venta >= %s")
        parametros.append(precio_min)
    if precio_max is not None:
        condiciones.append("precio_venta <= %s")
        parametros.append(precio_max)
    if skus is not None:
        condiciones.append(f"sku IN ({_marcadores(skus)})")
        parametros += skus

    sql = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    return sql, parametros


def listar(cursor, limite, offset, **filtros):
    """Página de productos y el total que cumple los filtros (AND entre todos)."""
    donde, parametros = _donde(**filtros)
    cursor.execute(f"SELECT COUNT(*) AS total FROM productos {donde}", parametros)
    total = cursor.fetchone()["total"]
    cursor.execute(
        f"SELECT {COLUMNAS} FROM productos {donde} {ORDEN} LIMIT %s OFFSET %s",
        [*parametros, limite, offset],
    )
    return cursor.fetchall(), total


def obtener(cursor, id_producto):
    cursor.execute(f"SELECT {COLUMNAS} FROM productos WHERE id_producto = %s", (id_producto,))
    return cursor.fetchone()


def obtener_por_sku(cursor, sku):
    """Datos que necesita ms-inventario. La comparación no distingue mayúsculas."""
    cursor.execute(f"SELECT {COLUMNAS_SKU} FROM productos WHERE sku = %s", (sku,))
    return cursor.fetchone()


def insertar(cursor, sku, nombre, descripcion, marca, id_categoria, unidad_medida,
             precio_venta, stock_minimo):
    """Inserta un producto ACTIVO y devuelve su id. Un SKU repetido lanza
    IntegrityError (errno 1062) por el índice único."""
    cursor.execute(
        "INSERT INTO productos (sku, nombre, descripcion, marca, id_categoria,"
        " unidad_medida, precio_venta, stock_minimo)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (sku, nombre, descripcion, marca, id_categoria, unidad_medida,
         precio_venta, stock_minimo),
    )
    return cursor.lastrowid


def obtener_bloqueando(cursor, id_producto):
    """Como `obtener`, pero bloquea la fila hasta el fin de la transacción."""
    cursor.execute(
        f"SELECT {COLUMNAS} FROM productos WHERE id_producto = %s FOR UPDATE",
        (id_producto,),
    )
    return cursor.fetchone()


def actualizar(cursor, id_producto, nombre, descripcion, marca, id_categoria,
               unidad_medida, precio_venta, stock_minimo):
    """Reemplaza los datos editables. El SKU y el estado no se tocan."""
    cursor.execute(
        "UPDATE productos SET nombre = %s, descripcion = %s, marca = %s,"
        " id_categoria = %s, unidad_medida = %s, precio_venta = %s, stock_minimo = %s"
        " WHERE id_producto = %s",
        (nombre, descripcion, marca, id_categoria, unidad_medida, precio_venta,
         stock_minimo, id_producto),
    )
