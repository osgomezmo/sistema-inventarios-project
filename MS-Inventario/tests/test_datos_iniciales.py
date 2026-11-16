"""Pruebas de los datos iniciales (D51).

Las de inserción corren en el MySQL de desarrollo dentro de una transacción que
siempre se revierte, con bodegas "ZZT-" y SKU "ZZTEST-", así que no dejan nada ni
tocan datos ajenos. Si MySQL no está disponible, esas pruebas se saltan.
"""

from decimal import Decimal

import pytest

from app.config import cargar_configuracion
from app.db import abrir_conexion
from app.errors import ApiError
from app.servicios.movimientos import ENTRADAS
from db import datos_iniciales as datos
from db.aplicar_migraciones import aplicar

CONFIG = cargar_configuracion()
PB, PS = "ZZT-", "ZZTEST-"


def test_datos_sin_prefijos_de_prueba_y_coherentes():
    codigos = [c for c, _, _ in datos.BODEGAS]
    assert codigos == ["BOD-PRINCIPAL", "BOD-SALA", "BOD-NORTE"]
    for sku, (unidad, minimo, costo) in datos.PRODUCTOS.items():
        assert not sku.startswith(("ZZ", "LT"))
        assert unidad in ("UNIDAD", "KILO", "LITRO") and Decimal(minimo) > 0 and Decimal(costo) > 0
        if unidad == "UNIDAD":
            assert Decimal(minimo) == Decimal(minimo).to_integral_value(), sku
    usados = {v[0] for v in datos.VENTAS + datos.VENTAS_FIN_DE_SEMANA} | {t[0] for t in datos.TRASLADOS}
    assert usados <= set(datos.PRODUCTOS)


@pytest.fixture(scope="module")
def config_mysql():
    try:
        abrir_conexion(CONFIG).close()
    except ApiError:
        pytest.skip("MySQL de desarrollo no disponible en 127.0.0.1:33062")
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


@pytest.fixture
def sembrado(cursor):
    aplicados = datos.insertar(cursor, prefijo_bodega=PB, prefijo_sku=PS)
    return cursor, aplicados


def saldos_de_prueba(cursor):
    cursor.execute(
        "SELECT s.sku, s.id_bodega, s.cantidad, s.costo_promedio, s.stock_minimo, b.codigo"
        " FROM saldos s JOIN bodegas b ON b.id_bodega = s.id_bodega"
        " WHERE b.codigo LIKE %s AND s.sku LIKE %s",
        ("ZZT-%", "ZZTEST-%"),
    )
    return cursor.fetchall()


def test_crea_bodegas_y_todos_los_movimientos(sembrado):
    cursor, aplicados = sembrado
    cursor.execute("SELECT codigo, estado FROM bodegas WHERE codigo LIKE %s ORDER BY id_bodega", ("ZZT-%",))
    assert [(f["codigo"], f["estado"]) for f in cursor.fetchall()] == [
        (PB + c, "ACTIVO") for c, _, _ in datos.BODEGAS]
    cursor.execute("SELECT tipo, COUNT(*) AS n FROM movimientos WHERE sku LIKE %s GROUP BY tipo", ("ZZTEST-%",))
    por_tipo = {f["tipo"]: f["n"] for f in cursor.fetchall()}
    assert por_tipo["TRASLADO_SALIDA"] == por_tipo["TRASLADO_ENTRADA"] == 2
    assert por_tipo["DEVOLUCION_CLIENTE"] == 1
    assert por_tipo["SALIDA"] == len(datos.VENTAS) + len(datos.VENTAS_FIN_DE_SEMANA)
    assert sum(por_tipo.values()) == aplicados
    cursor.execute("SELECT COUNT(*) AS n FROM movimientos WHERE sku LIKE %s AND motivo = %s"
                   " AND tipo = 'AJUSTE_POSITIVO' AND id_usuario = 1", ("ZZTEST-%", "inventario inicial"))
    assert cursor.fetchone()["n"] == por_tipo["AJUSTE_POSITIVO"]


def test_cada_saldo_es_la_suma_de_su_kardex(sembrado):
    cursor, _ = sembrado
    saldos = saldos_de_prueba(cursor)
    assert saldos
    for saldo in saldos:
        cursor.execute(
            "SELECT tipo, cantidad, saldo_resultante FROM movimientos WHERE sku = %s AND id_bodega = %s"
            " ORDER BY fecha, id_movimiento", (saldo["sku"], saldo["id_bodega"]))
        movimientos = cursor.fetchall()
        suma = sum((m["cantidad"] if m["tipo"] in ENTRADAS else -m["cantidad"] for m in movimientos), Decimal(0))
        assert suma == saldo["cantidad"] == movimientos[-1]["saldo_resultante"], saldo["sku"]
        assert saldo["cantidad"] >= 0


def test_costo_menor_que_el_precio_y_saldo_de_traslado(sembrado):
    cursor, _ = sembrado
    cursor.execute("SELECT documento_referencia FROM movimientos WHERE sku = %s AND tipo LIKE 'TRASLADO%%'",
                   (PS + "LAC-0001",))
    documentos = {f["documento_referencia"] for f in cursor.fetchall()}
    assert len(documentos) == 1 and documentos.pop().startswith("TR-")
    cursor.execute("SELECT documento_referencia FROM movimientos WHERE tipo = 'DEVOLUCION_CLIENTE' AND sku = %s",
                   (PS + "LAC-0004",))
    assert cursor.fetchone()["documento_referencia"] == "POS-000110"


def test_al_menos_dos_saldos_bajo_el_minimo_en_la_sala(sembrado):
    cursor, _ = sembrado
    bajos = [s for s in saldos_de_prueba(cursor) if s["cantidad"] <= s["stock_minimo"]]
    assert len(bajos) >= 2
    assert {s["codigo"] for s in bajos} == {PB + "BOD-SALA"}
    assert {s["sku"] for s in bajos} >= {PS + "BEB-0001", PS + "PAN-0001"}


def test_insertar_dos_veces_no_duplica(sembrado):
    cursor, _ = sembrado
    cursor.execute("SELECT COUNT(*) AS n FROM movimientos WHERE sku LIKE %s", ("ZZTEST-%",))
    antes = cursor.fetchone()["n"]

    assert datos.insertar(cursor, prefijo_bodega=PB, prefijo_sku=PS) == 0

    cursor.execute("SELECT COUNT(*) AS n FROM movimientos WHERE sku LIKE %s", ("ZZTEST-%",))
    assert cursor.fetchone()["n"] == antes
    cursor.execute("SELECT COUNT(*) AS n FROM bodegas WHERE codigo LIKE %s", ("ZZT-%",))
    assert cursor.fetchone()["n"] == 3


def test_base_vacia_mira_las_bodegas(cursor):
    cursor.execute("INSERT INTO bodegas (codigo, nombre, direccion) VALUES (%s, %s, %s)",
                   ("ZZT-DI-1", "Bodega", "Calle 1"))
    assert not datos.base_vacia(cursor)


def test_sembrar_solo_con_la_base_vacia(config_mysql, monkeypatch):
    llamadas = []
    monkeypatch.setattr(datos, "insertar", lambda cursor: llamadas.append(1) or 7)

    monkeypatch.setattr(datos, "base_vacia", lambda cursor: False)
    assert datos.sembrar(config_mysql) is None and llamadas == []

    monkeypatch.setattr(datos, "base_vacia", lambda cursor: True)
    assert datos.sembrar(config_mysql) == 7 and llamadas == [1]


def test_no_publica_eventos():
    texto = open(datos.__file__, encoding="utf-8").read()
    assert "publicar_movimiento" not in texto and "app.eventos" not in texto and "import eventos" not in texto
