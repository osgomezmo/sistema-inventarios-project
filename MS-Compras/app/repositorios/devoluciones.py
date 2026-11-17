"""Repositorio transaccional de devoluciones a proveedores."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.db import obtener_conexion, transaccion
from app.errors import ErrorAPI
from app.messaging.publicador import publicar_devolucion_registrada
from app.repositorios.ordenes import _obtener_detalles_orden, _obtener_orden_base


def registrar_devolucion(
    id_orden: int,
    payload: dict[str, Any],
    id_usuario: int,
) -> dict[str, Any]:
    """Registra una devolucion sobre mercancia recibida y publica el evento."""
    with transaccion() as (_conn, cursor):
        orden = _obtener_orden_base(cursor, id_orden, bloquear=True)
        if orden["estado"] not in {"RECIBIDA_PARCIAL", "RECIBIDA"}:
            raise ErrorAPI(
                409,
                "TRANSICION_INVALIDA",
                (
                    "Solo se pueden registrar devoluciones en ordenes "
                    f"con mercancia recibida (estado actual: {orden['estado']})."
                ),
                {"estado_actual": orden["estado"]},
            )

        detalles = _obtener_detalles_orden(cursor, id_orden, bloquear=True)
        mapa_detalles = {det["id_detalle"]: det for det in detalles}

        items_evento: list[dict[str, Any]] = []
        items_respuesta: list[dict[str, Any]] = []

        for item in payload["items"]:
            id_detalle = item["id_detalle"]
            cantidad: Decimal = item["cantidad"]
            detalle = mapa_detalles.get(id_detalle)
            if detalle is None:
                raise ErrorAPI(
                    422,
                    "DETALLE_NO_PERTENECE_ORDEN",
                    f"El detalle {id_detalle} no pertenece a la orden {id_orden}.",
                    {"id_detalle": id_detalle, "id_orden": id_orden},
                )

            disponible = detalle["cantidad_recibida"] - detalle["cantidad_devuelta"]
            if cantidad > disponible:
                raise ErrorAPI(
                    409,
                    "CANTIDAD_MAYOR_QUE_RECIBIDA",
                    (
                        f"La cantidad a devolver ({cantidad}) supera lo recibido "
                        f"disponible ({disponible}) para el SKU {detalle['sku']}."
                    ),
                    {
                        "id_detalle": id_detalle,
                        "sku": detalle["sku"],
                        "cantidad_solicitada": cantidad,
                        "disponible": disponible,
                    },
                )

        cursor.execute(
            """
            INSERT INTO devoluciones_proveedor (id_orden, motivo, id_usuario)
            VALUES (%s, %s, %s)
            """,
            (id_orden, payload["motivo"], id_usuario),
        )
        id_devolucion = int(cursor.lastrowid)

        for item in payload["items"]:
            id_detalle = item["id_detalle"]
            cantidad: Decimal = item["cantidad"]
            detalle = mapa_detalles[id_detalle]

            cursor.execute(
                """
                INSERT INTO devolucion_detalle (id_devolucion, id_detalle, cantidad)
                VALUES (%s, %s, %s)
                """,
                (id_devolucion, id_detalle, cantidad),
            )
            cursor.execute(
                """
                UPDATE detalles_orden
                SET cantidad_devuelta = cantidad_devuelta + %s
                WHERE id_detalle = %s
                """,
                (cantidad, id_detalle),
            )

            items_evento.append(
                {
                    "sku": detalle["sku"],
                    "cantidad": cantidad,
                }
            )
            items_respuesta.append(
                {
                    "id_detalle": id_detalle,
                    "sku": detalle["sku"],
                    "cantidad": cantidad,
                }
            )

        publicar_devolucion_registrada(
            id_orden=id_orden,
            id_devolucion=id_devolucion,
            id_bodega=orden["id_bodega_destino"],
            id_usuario=id_usuario,
            motivo=payload["motivo"],
            items=items_evento,
        )

        cursor.execute(
            """
            SELECT id_devolucion, id_orden, fecha, motivo, id_usuario
            FROM devoluciones_proveedor
            WHERE id_devolucion = %s
            """,
            (id_devolucion,),
        )
        devolucion = cursor.fetchone()
        devolucion["id_proveedor"] = orden["id_proveedor"]
        devolucion["id_bodega_destino"] = orden["id_bodega_destino"]
        devolucion["items"] = items_respuesta
        return devolucion


def listar_devoluciones(
    id_proveedor: int | None,
    desde: datetime | None,
    hasta: datetime | None,
    limite: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    """Lista devoluciones a proveedores filtradas y paginadas."""
    condiciones: list[str] = []
    parametros: list[Any] = []

    if id_proveedor is not None:
        condiciones.append("oc.id_proveedor = %s")
        parametros.append(id_proveedor)
    if desde is not None:
        condiciones.append("dp.fecha >= %s")
        parametros.append(desde)
    if hasta is not None:
        condiciones.append("dp.fecha <= %s")
        parametros.append(hasta)

    where_sql = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""

    with obtener_conexion() as (_conn, cursor):
        cursor.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM devoluciones_proveedor dp
            INNER JOIN ordenes_compra oc ON oc.id_orden = dp.id_orden
            {where_sql}
            """,
            tuple(parametros),
        )
        total = int(cursor.fetchone()["total"])

        cursor.execute(
            f"""
            SELECT
                dp.id_devolucion,
                dp.id_orden,
                oc.numero AS numero_orden,
                oc.id_proveedor,
                oc.id_bodega_destino,
                dp.fecha,
                dp.motivo,
                dp.id_usuario
            FROM devoluciones_proveedor dp
            INNER JOIN ordenes_compra oc ON oc.id_orden = dp.id_orden
            {where_sql}
            ORDER BY dp.fecha DESC, dp.id_devolucion DESC
            LIMIT %s OFFSET %s
            """,
            tuple([*parametros, limite, offset]),
        )
        devoluciones = list(cursor.fetchall())
        if not devoluciones:
            return [], total

        ids_devolucion = [dev["id_devolucion"] for dev in devoluciones]
        marcadores = ", ".join(["%s"] * len(ids_devolucion))
        cursor.execute(
            f"""
            SELECT
                dd.id_devolucion,
                dd.id_detalle,
                d.sku,
                dd.cantidad
            FROM devolucion_detalle dd
            INNER JOIN detalles_orden d ON d.id_detalle = dd.id_detalle
            WHERE dd.id_devolucion IN ({marcadores})
            ORDER BY dd.id_devolucion ASC, dd.id_detalle ASC
            """,
            tuple(ids_devolucion),
        )
        items_por_dev: dict[int, list[dict[str, Any]]] = {did: [] for did in ids_devolucion}
        for fila in cursor.fetchall():
            did = fila.pop("id_devolucion")
            items_por_dev.setdefault(did, []).append(fila)

        for dev in devoluciones:
            dev["items"] = items_por_dev.get(dev["id_devolucion"], [])

        return devoluciones, total
