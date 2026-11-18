"""Datos iniciales de ms-reportes coherentes con ms-productos, ms-inventario y ms-compras.

Uso, desde la carpeta del servicio:

    python -m db.datos_iniciales

Solo siembra si la tabla saldo_reporte esta vacia, en una sola transaccion,
para que el dashboard y los reportes tengan metricas iniciales aun cuando los
seeders de los otros microservicios insertan directo sin publicar en RabbitMQ.
"""

from datetime import datetime, timezone
from decimal import Decimal
import sys

from app.config import cargar_configuracion
from app.db import transaccion
from app.errors import ApiError

# Bodegas: 1 = BOD-PRINCIPAL, 2 = BOD-SALA, 3 = BOD-NORTE
# (sku, stock_minimo, costo_unitario)
PRODUCTOS = {
    "LAC-0001": ("24", "3450.0000"),
    "LAC-0002": ("24", "3950.0000"),
    "LAC-0003": ("20.500", "2900.0000"),
    "LAC-0004": ("10", "9100.0000"),
    "LAC-0005": ("4.500", "20500.0000"),
    "LAC-0006": ("12", "6900.0000"),
    "BEB-0001": ("30", "4600.0000"),
    "BEB-0002": ("30", "3300.0000"),
    "BEB-0003": ("20", "2950.0000"),
    "BEB-0004": ("15", "3650.0000"),
    "BEB-0005": ("48", "1100.0000"),
    "BEB-0006": ("24", "1300.0000"),
    "GRA-0001": ("40", "3300.0000"),
    "GRA-0002": ("10", "15800.0000"),
    "GRA-0003": ("15", "5600.0000"),
    "GRA-0004": ("8.500", "4700.0000"),
    "GRA-0005": ("12", "8500.0000"),
    "GRA-0006": ("6", "23900.0000"),
    "ASE-0001": ("10", "17200.0000"),
    "ASE-0002": ("8", "20100.0000"),
    "ASE-0003": ("30", "2200.0000"),
    "ASE-0004": ("20", "2700.0000"),
    "ASE-0005": ("6.000", "5300.0000"),
    "PAN-0001": ("15", "5600.0000"),
    "PAN-0002": ("50", "350.0000"),
    "PAN-0003": ("10", "3100.0000"),
    "CAR-0001": ("5.000", "19800.0000"),
    "CAR-0002": ("3.500", "32400.0000"),
    "CAR-0003": ("6.000", "13900.0000"),
    "CAR-0004": ("8.000", "9300.0000"),
    "FRU-0001": ("10.000", "2100.0000"),
    "FRU-0002": ("20.000", "1800.0000"),
    "FRU-0003": ("8.500", "3000.0000"),
}

NORTE = ("BEB-", "GRA-", "ASE-")

VENTAS = [
    ("LAC-0001", "5"),
    ("BEB-0003", "4"),
    ("GRA-0001", "6"),
    ("ASE-0003", "5"),
    ("FRU-0001", "2.500"),
    ("CAR-0001", "1.250"),
    ("LAC-0005", "0.750"),
    ("BEB-0001", "35"),
    ("PAN-0001", "18"),
]

TRASLADOS = [
    ("LAC-0001", 1, 2, "24"),
    ("GRA-0001", 3, 2, "20"),
]

DEVOLUCION_CLIENTE = ("LAC-0004", 2, "1")

ORDENES_INICIALES = [
    ("OC-2026-000001", 1, 1, "RECIBIDA", "549300.00"),
    ("OC-2026-000002", 2, 2, "RECIBIDA_PARCIAL", "381600.00"),
    ("OC-2026-000003", 3, 3, "APROBADA", "608000.00"),
    ("OC-2026-000004", 4, 4, "BORRADOR", "220500.00"),
    ("OC-2026-000005", 5, 2, "ANULADA", "99000.00"),
]


def _construir_proyecciones():
    """Calcula saldos finales, movimientos diarios y alertas bajo minimo."""
    saldos = {}  # (sku, id_bodega) -> [cantidad, costo, entradas, salidas, minimo]

    for sku, (min_str, costo_str) in PRODUCTOS.items():
        minimo = Decimal(min_str)
        costo = Decimal(costo_str)
        inicial = {1: minimo * 6, 2: minimo * 2}
        if sku.startswith(NORTE):
            inicial[3] = minimo * 3
        for id_bodega, cant in inicial.items():
            saldos[(sku, id_bodega)] = [cant, costo, cant, Decimal("0.000"), minimo]

    for sku, cant_str in VENTAS:
        cant = Decimal(cant_str)
        reg = saldos[(sku, 2)]
        reg[0] -= cant
        reg[3] += cant

    for sku, origen, destino, cant_str in TRASLADOS:
        cant = Decimal(cant_str)
        saldos[(sku, origen)][0] -= cant
        saldos[(sku, origen)][3] += cant
        saldos[(sku, destino)][0] += cant
        saldos[(sku, destino)][2] += cant

    sku_dev, bod_dev, cant_dev_str = DEVOLUCION_CLIENTE
    cant_dev = Decimal(cant_dev_str)
    saldos[(sku_dev, bod_dev)][0] += cant_dev
    saldos[(sku_dev, bod_dev)][2] += cant_dev

    return saldos


def base_vacia(cursor):
    cursor.execute("SELECT COUNT(*) AS n FROM saldo_reporte")
    fila = cursor.fetchone()
    return int(fila["n"] if isinstance(fila, dict) else fila[0]) == 0


def insertar(cursor, fecha_mov=None):
    """Inserta los saldos, movimientos diarios, alertas y ordenes iniciales."""
    fecha = fecha_mov or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    saldos = _construir_proyecciones()

    insertados_saldos = 0
    insertados_alertas = 0

    for (sku, id_bodega), (cantidad, costo, entradas, salidas, minimo) in saldos.items():
        valor_total = (cantidad * costo).quantize(Decimal("0.01"))
        cursor.execute(
            """
            INSERT INTO saldo_reporte (sku, id_bodega, cantidad, costo_promedio, valor_total, actualizado_en)
            VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP())
            ON DUPLICATE KEY UPDATE
                cantidad = VALUES(cantidad),
                costo_promedio = VALUES(costo_promedio),
                valor_total = VALUES(valor_total),
                actualizado_en = UTC_TIMESTAMP()
            """,
            (sku, id_bodega, cantidad, costo, valor_total),
        )
        insertados_saldos += 1

        cursor.execute(
            """
            INSERT INTO movimiento_diario (sku, id_bodega, fecha, entradas, salidas)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                entradas = VALUES(entradas),
                salidas = VALUES(salidas)
            """,
            (sku, id_bodega, fecha, entradas, salidas),
        )

        if cantidad <= minimo:
            cursor.execute(
                """
                INSERT INTO alerta_stock (sku, id_bodega, saldo, stock_minimo, activa, fecha)
                VALUES (%s, %s, %s, %s, 1, UTC_TIMESTAMP())
                ON DUPLICATE KEY UPDATE
                    saldo = VALUES(saldo),
                    stock_minimo = VALUES(stock_minimo),
                    activa = 1,
                    fecha = UTC_TIMESTAMP()
                """,
                (sku, id_bodega, cantidad, minimo),
            )
            insertados_alertas += 1

    for numero, id_orden, id_proveedor, estado, total in ORDENES_INICIALES:
        cursor.execute(
            """
            INSERT INTO orden_pendiente (id_orden, numero, id_proveedor, estado, total, actualizada_en)
            VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP())
            ON DUPLICATE KEY UPDATE
                numero = COALESCE(VALUES(numero), numero),
                id_proveedor = VALUES(id_proveedor),
                estado = VALUES(estado),
                total = VALUES(total),
                actualizada_en = UTC_TIMESTAMP()
            """,
            (id_orden, numero, id_proveedor, estado, Decimal(total)),
        )

    return insertados_saldos, insertados_alertas, len(ORDENES_INICIALES)


def sembrar(config=None):
    """Siembra solo si saldo_reporte esta vacia. Devuelve tupla o None."""
    config = config if config is not None else cargar_configuracion()
    with transaccion(config) as cursor:
        cursor.execute("SELECT nombre FROM migraciones_aplicadas FOR UPDATE")
        cursor.fetchall()
        if not base_vacia(cursor):
            return None
        return insertar(cursor)


def main():
    try:
        resultado = sembrar()
    except ApiError as error:
        print(f"[ms-reportes] No se sembraron los datos iniciales: {error.mensaje}", file=sys.stderr)
        return 1
    if resultado is None:
        print("[ms-reportes] La base ya tiene datos: no se siembran datos iniciales.")
    else:
        saldos, alertas, ordenes = resultado
        print(
            f"[ms-reportes] Datos iniciales sembrados: {saldos} saldos, "
            f"{alertas} alertas de stock bajo y {ordenes} ordenes."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
