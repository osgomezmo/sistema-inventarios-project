"""Datos iniciales de ms-compras: ordenes de compra, recepciones y devoluciones.

Uso, desde la carpeta del servicio:

    python -m db.datos_iniciales

Solo siembra si la tabla ordenes_compra esta vacia, en una sola transaccion y
sin publicar eventos en RabbitMQ.
"""

from decimal import Decimal
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
import mysql.connector

DIRECTORIO_RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(DIRECTORIO_RAIZ / ".env")

ORDENES_INICIALES = [
    {
        "numero": "OC-2026-000001",
        "id_proveedor": 1,
        "id_bodega_destino": 1,
        "estado": "RECIBIDA",
        "id_usuario_creador": 1,
        "id_usuario_aprobador": 1,
        "motivo_anulacion": None,
        "items": [
            ("LAC-0001", "48.000", "48.000", "0.000", "3450.00"),
            ("LAC-0004", "20.000", "20.000", "2.000", "9100.00"),
            ("CAR-0001", "10.000", "10.000", "0.000", "19800.00"),
        ],
        "recepciones": [
            {
                "id_usuario": 1,
                "observaciones": "Entrega completa en furgon refrigerado.",
                "items": [
                    ("LAC-0001", "48.000"),
                    ("LAC-0004", "20.000"),
                    ("CAR-0001", "10.000"),
                ],
            }
        ],
        "devoluciones": [
            {
                "id_usuario": 1,
                "motivo": "Dos empaques con sello roto al verificar lote.",
                "items": [
                    ("LAC-0004", "2.000"),
                ],
            }
        ],
    },
    {
        "numero": "OC-2026-000002",
        "id_proveedor": 2,
        "id_bodega_destino": 1,
        "estado": "RECIBIDA_PARCIAL",
        "id_usuario_creador": 1,
        "id_usuario_aprobador": 1,
        "motivo_anulacion": None,
        "items": [
            ("BEB-0001", "60.000", "40.000", "0.000", "4600.00"),
            ("BEB-0005", "96.000", "96.000", "0.000", "1100.00"),
        ],
        "recepciones": [
            {
                "id_usuario": 1,
                "observaciones": "Primera entrega parcial de bebidas.",
                "items": [
                    ("BEB-0001", "40.000"),
                    ("BEB-0005", "96.000"),
                ],
            }
        ],
        "devoluciones": [],
    },
    {
        "numero": "OC-2026-000003",
        "id_proveedor": 3,
        "id_bodega_destino": 3,
        "estado": "APROBADA",
        "id_usuario_creador": 1,
        "id_usuario_aprobador": 1,
        "motivo_anulacion": None,
        "items": [
            ("GRA-0001", "80.000", "0.000", "0.000", "3300.00"),
            ("ASE-0001", "20.000", "0.000", "0.000", "17200.00"),
        ],
        "recepciones": [],
        "devoluciones": [],
    },
    {
        "numero": "OC-2026-000004",
        "id_proveedor": 4,
        "id_bodega_destino": 2,
        "estado": "BORRADOR",
        "id_usuario_creador": 1,
        "id_usuario_aprobador": None,
        "motivo_anulacion": None,
        "items": [
            ("PAN-0001", "30.000", "0.000", "0.000", "5600.00"),
            ("FRU-0001", "25.000", "0.000", "0.000", "2100.00"),
        ],
        "recepciones": [],
        "devoluciones": [],
    },
    {
        "numero": "OC-2026-000005",
        "id_proveedor": 2,
        "id_bodega_destino": 1,
        "estado": "ANULADA",
        "id_usuario_creador": 1,
        "id_usuario_aprobador": None,
        "motivo_anulacion": "Solicitud duplicada reemplazada por OC-2026-000002.",
        "items": [
            ("BEB-0002", "30.000", "0.000", "0.000", "3300.00"),
        ],
        "recepciones": [],
        "devoluciones": [],
    },
]


def insertar(cursor, ordenes=ORDENES_INICIALES) -> int:
    """Inserta las ordenes iniciales si no existen. Devuelve cantidad insertada."""
    insertadas = 0
    for orden in ordenes:
        cursor.execute("SELECT id_orden FROM ordenes_compra WHERE numero = %s", (orden["numero"],))
        if cursor.fetchone():
            continue

        total = sum(
            Decimal(cant_ped) * Decimal(precio)
            for _sku, cant_ped, _cant_rec, _cant_dev, precio in orden["items"]
        ).quantize(Decimal("0.01"))

        aprobada_sql = "UTC_TIMESTAMP()" if orden["id_usuario_aprobador"] is not None else "NULL"
        cursor.execute(
            f"""
            INSERT INTO ordenes_compra (
                numero, id_proveedor, id_bodega_destino, estado, total,
                id_usuario_creador, id_usuario_aprobador, motivo_anulacion,
                creada_en, aprobada_en, actualizada_en
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, UTC_TIMESTAMP(), {aprobada_sql}, UTC_TIMESTAMP())
            """,
            (
                orden["numero"],
                orden["id_proveedor"],
                orden["id_bodega_destino"],
                orden["estado"],
                str(total),
                orden["id_usuario_creador"],
                orden["id_usuario_aprobador"],
                orden["motivo_anulacion"],
            ),
        )
        id_orden = int(cursor.lastrowid)
        insertadas += 1

        id_detalle_por_sku = {}
        for sku, cant_ped, cant_rec, cant_dev, precio in orden["items"]:
            cursor.execute(
                """
                INSERT INTO detalles_orden (
                    id_orden, sku, cantidad_pedida, cantidad_recibida,
                    cantidad_devuelta, precio_unitario
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (id_orden, sku, cant_ped, cant_rec, cant_dev, precio),
            )
            id_detalle_por_sku[sku] = int(cursor.lastrowid)

        for rec in orden.get("recepciones", []):
            cursor.execute(
                """
                INSERT INTO recepciones (id_orden, fecha, id_usuario, observaciones)
                VALUES (%s, UTC_TIMESTAMP(), %s, %s)
                """,
                (id_orden, rec["id_usuario"], rec["observaciones"]),
            )
            id_recepcion = int(cursor.lastrowid)
            for sku, cant in rec["items"]:
                cursor.execute(
                    """
                    INSERT INTO recepcion_detalle (id_recepcion, id_detalle, cantidad)
                    VALUES (%s, %s, %s)
                    """,
                    (id_recepcion, id_detalle_por_sku[sku], cant),
                )

        for dev in orden.get("devoluciones", []):
            cursor.execute(
                """
                INSERT INTO devoluciones_proveedor (id_orden, fecha, motivo, id_usuario)
                VALUES (%s, UTC_TIMESTAMP(), %s, %s)
                """,
                (id_orden, dev["motivo"], dev["id_usuario"]),
            )
            id_devolucion = int(cursor.lastrowid)
            for sku, cant in dev["items"]:
                cursor.execute(
                    """
                    INSERT INTO devolucion_detalle (id_devolucion, id_detalle, cantidad)
                    VALUES (%s, %s, %s)
                    """,
                    (id_devolucion, id_detalle_por_sku[sku], cant),
                )

    return insertadas


def sembrar() -> int | None:
    """Siembra solo si ordenes_compra esta vacia. Devuelve cantidad o None."""
    conexion = mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "compras_user"),
        password=os.getenv("DB_PASSWORD", "changeme"),
        database=os.getenv("DB_NAME", "mscompras"),
        time_zone="+00:00",
        charset="utf8mb4",
        collation="utf8mb4_0900_ai_ci",
        autocommit=False,
    )
    try:
        cursor = conexion.cursor(dictionary=True)
        try:
            cursor.execute("SELECT version FROM schema_migrations FOR UPDATE")
            cursor.fetchall()
            cursor.execute("SELECT COUNT(*) AS n FROM ordenes_compra")
            if int(cursor.fetchone()["n"]) > 0:
                conexion.rollback()
                return None
            insertadas = insertar(cursor)
            conexion.commit()
            return insertadas
        except Exception:
            conexion.rollback()
            raise
        finally:
            cursor.close()
    finally:
        conexion.close()


def main() -> int:
    try:
        insertadas = sembrar()
    except Exception as exc:
        print(f"[ms-compras] No se sembraron los datos iniciales: {exc}", file=sys.stderr)
        return 1
    if insertadas is None:
        print("[ms-compras] La base ya tiene ordenes: no se siembran datos iniciales.")
    else:
        print(f"[ms-compras] Datos iniciales sembrados: {insertadas} ordenes de compra.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
