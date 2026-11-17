"""Pruebas de los datos iniciales (D51).

Las de estructura no usan la base. Las de inserción corren en el MySQL de
desarrollo dentro de una transacción que siempre se revierte, con copias de los
datos con prefijos de prueba ("zz_test_" y "ZZTEST-"), así que no dejan nada ni
tocan datos ajenos. Si MySQL no está disponible, esas pruebas se saltan.
"""

from collections import Counter
from decimal import Decimal

import pytest

from app.config import cargar_configuracion
from app.db import abrir_conexion
from app.errors import ApiError
from db import datos_iniciales as datos
from db.aplicar_migraciones import aplicar

CONFIG = cargar_configuracion()
SKU_VALIDO = r"^[A-Z]{3}-\d{4}$"


# --- Estructura de los datos ---------------------------------------------------------


def test_sku_unicos_y_con_prefijo_de_su_categoria():
    skus = [p[0] for p in datos.PRODUCTOS]
    assert len(skus) == len(set(skus)) and 25 <= len(skus) <= 40
    prefijos = {"Lácteos": "LAC", "Bebidas": "BEB", "Granos y abarrotes": "GRA", "Aseo": "ASE",
                "Panadería": "PAN", "Carnes": "CAR", "Frutas y verduras": "FRU"}
    for sku, _, _, (raiz, _), *_ in datos.PRODUCTOS:
        assert sku.startswith(prefijos[raiz] + "-") and len(sku) == 8


def test_cada_producto_apunta_a_una_categoria_definida():
    for _, _, _, (raiz, sub), *_ in datos.PRODUCTOS:
        assert raiz in datos.CATEGORIAS
        assert sub is None or sub in datos.CATEGORIAS[raiz]


def test_unidades_precios_y_minimos_coherentes():
    for sku, _, marca, _, unidad, precio, minimo, estado in datos.PRODUCTOS:
        assert unidad in ("UNIDAD", "KILO", "LITRO") and marca
        assert Decimal(precio) > 0 and Decimal(precio).as_tuple().exponent == -2
        assert Decimal(minimo) > 0
        if unidad == "UNIDAD":
            assert Decimal(minimo) == Decimal(minimo).to_integral_value(), sku
        assert estado in ("ACTIVO", "INACTIVO")
    estados = Counter(p[7] for p in datos.PRODUCTOS)
    assert 1 <= estados["INACTIVO"] <= 2
    assert {p[4] for p in datos.PRODUCTOS} == {"UNIDAD", "KILO", "LITRO"}


def test_sin_prefijos_de_datos_de_prueba():
    textos = [p[0] for p in datos.PRODUCTOS] + list(datos.CATEGORIAS)
    textos += [s for subs in datos.CATEGORIAS.values() for s in subs]
    for texto in textos:
        assert not texto.upper().startswith(("ZZT", "ZZ_TEST", "LT-", "LT "))


# --- Inserción contra MySQL (transacción revertida) ----------------------------------


@pytest.fixture(scope="module")
def config_mysql():
    try:
        abrir_conexion(CONFIG).close()
    except ApiError:
        pytest.skip("MySQL de desarrollo no disponible en 127.0.0.1:33061")
    aplicar(CONFIG)
    return CONFIG


@pytest.fixture
def cursor(config_mysql):
    conexion = abrir_conexion(config_mysql)
    conexion.start_transaction()
    cur = conexion.cursor(dictionary=True)
    try:
        yield cur
    finally:
        cur.close()
        conexion.rollback()  # no queda nada de la prueba
        conexion.close()


def con_prefijo():
    """Copia de los datos con prefijos de prueba, para no chocar con los reales."""
    nombre = lambda n: f"zz_test_{n}"  # noqa: E731
    categorias = {nombre(r): [nombre(s) for s in subs] for r, subs in datos.CATEGORIAS.items()}
    productos = [
        (f"ZZTEST-{sku}", n, marca, (nombre(r), nombre(s) if s else None), u, p, m, e)
        for sku, n, marca, (r, s), u, p, m, e in datos.PRODUCTOS
    ]
    descripciones = {nombre(r): d for r, d in datos.DESCRIPCIONES.items()}
    return categorias, productos, descripciones


def contar(cursor):
    cursor.execute("SELECT COUNT(*) AS n FROM categorias WHERE nombre LIKE %s", ("zz\\_test\\_%",))
    categorias = cursor.fetchone()["n"]
    cursor.execute("SELECT COUNT(*) AS n FROM productos WHERE sku LIKE %s", ("ZZTEST-%",))
    return categorias, cursor.fetchone()["n"]


def test_inserta_la_jerarquia_y_los_productos(cursor):
    categorias, productos, descripciones = con_prefijo()
    total_categorias = sum(len(s) + 1 for s in categorias.values())

    _, nuevos = datos.insertar(cursor, categorias, productos, descripciones)

    assert nuevos == len(productos)
    assert contar(cursor) == (total_categorias, len(productos))
    cursor.execute(
        "SELECT p.unidad_medida, p.precio_venta, p.stock_minimo, p.estado, c.nombre AS categoria,"
        " padre.nombre AS raiz FROM productos p JOIN categorias c ON c.id_categoria = p.id_categoria"
        " LEFT JOIN categorias padre ON padre.id_categoria = c.id_categoria_padre WHERE p.sku = %s",
        ("ZZTEST-LAC-0005",),
    )
    queso = cursor.fetchone()
    assert (queso["categoria"], queso["raiz"]) == ("zz_test_Quesos", "zz_test_Lácteos")
    assert queso["unidad_medida"] == "KILO" and queso["precio_venta"] == Decimal("28500.00")
    assert queso["stock_minimo"] == Decimal("4.500") and queso["estado"] == "ACTIVO"
    cursor.execute("SELECT estado FROM productos WHERE sku = %s", ("ZZTEST-BEB-0006",))
    assert cursor.fetchone()["estado"] == "INACTIVO"
    cursor.execute("SELECT id_categoria_padre FROM categorias WHERE nombre = %s", ("zz_test_Panadería",))
    assert cursor.fetchone()["id_categoria_padre"] is None


def test_insertar_dos_veces_no_duplica(cursor):
    categorias, productos, descripciones = con_prefijo()
    datos.insertar(cursor, categorias, productos, descripciones)
    antes = contar(cursor)

    _, nuevos = datos.insertar(cursor, categorias, productos, descripciones)

    assert nuevos == 0 and contar(cursor) == antes


def test_base_vacia_mira_las_categorias(cursor):
    cursor.execute("INSERT INTO categorias (nombre) VALUES (%s)", ("zz_test_cualquiera",))
    assert not datos.base_vacia(cursor)


def test_sembrar_no_hace_nada_si_ya_hay_categorias(config_mysql, monkeypatch):
    """Con categorías en la base, sembrar no llama a insertar."""
    llamadas = []
    monkeypatch.setattr(datos, "base_vacia", lambda cursor: False)
    monkeypatch.setattr(datos, "insertar", lambda cursor: llamadas.append(1))

    assert datos.sembrar(config_mysql) is False
    assert llamadas == []


def test_sembrar_inserta_si_la_base_esta_vacia(config_mysql, monkeypatch):
    llamadas = []
    monkeypatch.setattr(datos, "base_vacia", lambda cursor: True)
    monkeypatch.setattr(datos, "insertar", lambda cursor: llamadas.append(1))

    assert datos.sembrar(config_mysql) is True
    assert llamadas == [1]
