"""Datos iniciales de ms-productos: categorías y productos de un supermercado (D51).

Uso, desde la carpeta del servicio:

    python -m db.datos_iniciales

Solo siembra si la base no tiene categorías, así que correrlo de nuevo (o
reiniciar el contenedor) no duplica nada. Todo va en una sola transacción.
"""

import sys
from decimal import Decimal

from app.config import cargar_configuracion
from app.db import transaccion
from app.errors import ApiError

# Raíz: subcategorías (una lista vacía es una categoría sin subcategorías)
CATEGORIAS = {
    "Lácteos": ["Leches", "Quesos", "Yogures"],
    "Bebidas": ["Gaseosas", "Jugos", "Aguas"],
    "Granos y abarrotes": ["Arroz", "Fríjol y lenteja", "Aceites"],
    "Aseo": ["Detergentes", "Jabones"],
    "Panadería": [],
    "Carnes": ["Res", "Pollo"],
    "Frutas y verduras": [],
}

DESCRIPCIONES = {
    "Lácteos": "Leches, quesos, yogures y derivados.",
    "Bebidas": "Gaseosas, jugos y aguas.",
    "Granos y abarrotes": "Arroz, granos, aceites y productos de despensa.",
    "Aseo": "Aseo del hogar y cuidado personal.",
    "Panadería": "Pan fresco y empacado.",
    "Carnes": "Carnes rojas y pollo.",
    "Frutas y verduras": "Frutas, verduras y tubérculos frescos.",
}

# (sku, nombre, marca, categoría (raíz, subcategoría o None), unidad, precio, stock mínimo, estado)
PRODUCTOS = [
    ("LAC-0001", "Leche entera bolsa 1100 ml", "Alquería", ("Lácteos", "Leches"), "UNIDAD", "4900.00", "24", "ACTIVO"),
    ("LAC-0002", "Leche deslactosada 1 L", "Colanta", ("Lácteos", "Leches"), "UNIDAD", "5600.00", "24", "ACTIVO"),
    ("LAC-0003", "Leche entera a granel", "Colanta", ("Lácteos", "Leches"), "LITRO", "4200.00", "20.500", "ACTIVO"),
    ("LAC-0004", "Queso campesino 500 g", "Colanta", ("Lácteos", "Quesos"), "UNIDAD", "12900.00", "10", "ACTIVO"),
    ("LAC-0005", "Queso doble crema por kilo", "Alpina", ("Lácteos", "Quesos"), "KILO", "28500.00", "4.500", "ACTIVO"),
    ("LAC-0006", "Yogur de fresa 1 L", "Alpina", ("Lácteos", "Yogures"), "UNIDAD", "9800.00", "12", "ACTIVO"),
    ("BEB-0001", "Gaseosa Coca-Cola 1,5 L", "Coca-Cola", ("Bebidas", "Gaseosas"), "UNIDAD", "6500.00", "30", "ACTIVO"),
    ("BEB-0002", "Gaseosa Manzana 1,5 L", "Postobón", ("Bebidas", "Gaseosas"), "UNIDAD", "4800.00", "30", "ACTIVO"),
    ("BEB-0003", "Jugo de mora 1 L", "Hit", ("Bebidas", "Jugos"), "UNIDAD", "4200.00", "20", "ACTIVO"),
    ("BEB-0004", "Jugo de naranja 1 L", "Del Valle", ("Bebidas", "Jugos"), "UNIDAD", "5200.00", "15", "ACTIVO"),
    ("BEB-0005", "Agua sin gas 600 ml", "Cristal", ("Bebidas", "Aguas"), "UNIDAD", "1800.00", "48", "ACTIVO"),
    ("BEB-0006", "Agua con gas 600 ml", "Brisa", ("Bebidas", "Aguas"), "UNIDAD", "2000.00", "24", "INACTIVO"),
    ("GRA-0001", "Arroz blanco 1 kg", "Diana", ("Granos y abarrotes", "Arroz"), "UNIDAD", "4600.00", "40", "ACTIVO"),
    ("GRA-0002", "Arroz blanco 5 kg", "Roa", ("Granos y abarrotes", "Arroz"), "UNIDAD", "21500.00", "10", "ACTIVO"),
    ("GRA-0003", "Fríjol cargamanto 500 g", "Diana", ("Granos y abarrotes", "Fríjol y lenteja"), "UNIDAD", "7900.00", "15", "ACTIVO"),
    ("GRA-0004", "Lenteja a granel", "Granel", ("Granos y abarrotes", "Fríjol y lenteja"), "KILO", "6800.00", "8.500", "ACTIVO"),
    ("GRA-0005", "Aceite de girasol 900 ml", "Premier", ("Granos y abarrotes", "Aceites"), "UNIDAD", "11900.00", "12", "ACTIVO"),
    ("GRA-0006", "Aceite vegetal 3 L", "Gourmet", ("Granos y abarrotes", "Aceites"), "UNIDAD", "32500.00", "6", "ACTIVO"),
    ("ASE-0001", "Detergente en polvo 2 kg", "Fab", ("Aseo", "Detergentes"), "UNIDAD", "23900.00", "10", "ACTIVO"),
    ("ASE-0002", "Detergente líquido 1,8 L", "Ariel", ("Aseo", "Detergentes"), "UNIDAD", "27900.00", "8", "ACTIVO"),
    ("ASE-0003", "Jabón en barra 300 g", "Rey", ("Aseo", "Jabones"), "UNIDAD", "3200.00", "30", "ACTIVO"),
    ("ASE-0004", "Jabón de tocador avena 110 g", "Protex", ("Aseo", "Jabones"), "UNIDAD", "3900.00", "20", "ACTIVO"),
    ("ASE-0005", "Desinfectante lavanda a granel", "Fabuloso", ("Aseo", "Detergentes"), "LITRO", "7800.00", "6.000", "ACTIVO"),
    ("PAN-0001", "Pan tajado 600 g", "Bimbo", ("Panadería", None), "UNIDAD", "7900.00", "15", "ACTIVO"),
    ("PAN-0002", "Pan francés", "Panadería de la casa", ("Panadería", None), "UNIDAD", "600.00", "50", "ACTIVO"),
    ("PAN-0003", "Mogolla integral x 6", "Comapan", ("Panadería", None), "UNIDAD", "4500.00", "10", "INACTIVO"),
    ("CAR-0001", "Carne de res molida", "Colanta", ("Carnes", "Res"), "KILO", "26900.00", "5.000", "ACTIVO"),
    ("CAR-0002", "Lomo de res", "Colanta", ("Carnes", "Res"), "KILO", "42900.00", "3.500", "ACTIVO"),
    ("CAR-0003", "Pechuga de pollo", "Mac Pollo", ("Carnes", "Pollo"), "KILO", "18900.00", "6.000", "ACTIVO"),
    ("CAR-0004", "Pollo entero", "Pimpollo", ("Carnes", "Pollo"), "KILO", "12900.00", "8.000", "ACTIVO"),
    ("FRU-0001", "Banano", "Granel", ("Frutas y verduras", None), "KILO", "3200.00", "10.000", "ACTIVO"),
    ("FRU-0002", "Papa pastusa", "Granel", ("Frutas y verduras", None), "KILO", "2900.00", "20.000", "ACTIVO"),
    ("FRU-0003", "Tomate chonto", "Granel", ("Frutas y verduras", None), "KILO", "4500.00", "8.500", "ACTIVO"),
]


def base_vacia(cursor):
    cursor.execute("SELECT COUNT(*) AS n FROM categorias")
    return cursor.fetchone()["n"] == 0


def _id_categoria(cursor, nombre, id_padre):
    """Busca la categoría por nombre en su nivel; None si no existe."""
    if id_padre is None:
        cursor.execute("SELECT id_categoria FROM categorias WHERE nombre = %s AND id_categoria_padre IS NULL",
                       (nombre,))
    else:
        cursor.execute("SELECT id_categoria FROM categorias WHERE nombre = %s AND id_categoria_padre = %s",
                       (nombre, id_padre))
    fila = cursor.fetchone()
    return fila["id_categoria"] if fila else None


def _asegurar_categoria(cursor, nombre, id_padre, descripcion):
    id_categoria = _id_categoria(cursor, nombre, id_padre)
    if id_categoria is None:
        cursor.execute(
            "INSERT INTO categorias (nombre, descripcion, id_categoria_padre) VALUES (%s, %s, %s)",
            (nombre, descripcion, id_padre),
        )
        id_categoria = cursor.lastrowid
    return id_categoria


def insertar(cursor, categorias=CATEGORIAS, productos=PRODUCTOS, descripciones=DESCRIPCIONES):
    """Inserta lo que falte (no repite categorías por nivel ni SKU).

    Devuelve (categorías nuevas o existentes, productos insertados).
    """
    ids = {}
    for raiz, subcategorias in categorias.items():
        id_raiz = _asegurar_categoria(cursor, raiz, None, descripciones.get(raiz))
        ids[(raiz, None)] = id_raiz
        for sub in subcategorias:
            ids[(raiz, sub)] = _asegurar_categoria(cursor, sub, id_raiz, None)

    nuevos = 0
    for sku, nombre, marca, categoria, unidad, precio, minimo, estado in productos:
        cursor.execute("SELECT 1 FROM productos WHERE sku = %s", (sku,))
        if cursor.fetchone():
            continue
        cursor.execute(
            "INSERT INTO productos (sku, nombre, descripcion, marca, id_categoria, unidad_medida,"
            " precio_venta, stock_minimo, estado) VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s)",
            (sku, nombre, marca, ids[categoria], unidad, Decimal(precio), Decimal(minimo), estado),
        )
        nuevos += 1
    return len(ids), nuevos


def sembrar(config=None):
    """Siembra solo si no hay categorías. Devuelve True si sembró."""
    config = config if config is not None else cargar_configuracion()
    with transaccion(config) as cursor:
        # Bloqueo de la tabla de registro: dos arranques simultáneos no siembran dos veces
        cursor.execute("SELECT nombre FROM migraciones_aplicadas FOR UPDATE")
        cursor.fetchall()
        if not base_vacia(cursor):
            return False
        insertar(cursor)
    return True


def main():
    try:
        sembro = sembrar()
    except ApiError as error:
        print(f"No se sembraron los datos iniciales: {error.mensaje}", file=sys.stderr)
        return 1
    if sembro:
        print(f"Datos iniciales: {sum(len(s) + 1 for s in CATEGORIAS.values())} categorías y "
              f"{len(PRODUCTOS)} productos.")
    else:
        print("La base ya tiene categorías: no se siembran datos iniciales.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
