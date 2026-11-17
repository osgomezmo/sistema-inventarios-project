"""Repositorio transaccional de recepciones de mercancia."""

from decimal import Decimal
from typing import Any

from app.db import obtener_conexion, transaccion
from app.errors import ErrorAPI
from app.messaging.publicador import (
    publicar_mercancia_recibida,
    publicar_orden_actualizada,
)
from app.repositorios.ordenes import _obtener_detalles_orden, _obtener_orden_base


def registrar_recepcion(
    id_orden: int,
    payload: dict[str, Any],
    id_usuario: int,
) -> dict[str, Any]:
    """Registra una recepcion parcial o total y publica los eventos correspondientes."""
    with transaccion() as (_conn, cursor):
        orden = _obtener_orden_base(cursor, id_orden, bloquear=True)
        if orden["estado"] not in {"APROBADA", "RECIBIDA_PARCIAL"}:
            raise ErrorAPI(
                409,
                "ORDEN_NO_APROBADA",
                f"No se puede recibir mercancia de una orden en estado {orden['estado']}.",
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

            pendiente = detalle["cantidad_pedida"] - detalle["cantidad_recibida"]
            if cantidad > pendiente:
                raise ErrorAPI(
                    409,
                    "CANTIDAD_MAYOR_QUE_PENDIENTE",
                    (
                        f"La cantidad recibida ({cantidad}) supera la pendiente "
                        f"({pendiente}) para el SKU {detalle['sku']}."
                    ),
                    {
                        "id_detalle": id_detalle,
                        "sku": detalle["sku"],
                        "cantidad_solicitada": cantidad,
                        "pendiente": pendiente,
                    },
                )

        cursor.execute(
            """
            INSERT INTO recepciones (id_orden, id_usuario, observaciones)
            VALUES (%s, %s, %s)
            """,
            (id_orden, id_usuario, payload["observaciones"]),
        )
        id_recepcion = int(cursor.lastrowid)

        for item in payload["items"]:
            id_detalle = item["id_detalle"]
            cantidad: Decimal = item["cantidad"]
            detalle = mapa_detalles[id_detalle]

            cursor.execute(
                """
                INSERT INTO recepcion_detalle (id_recepcion, id_detalle, cantidad)
                VALUES (%s, %s, %s)
                """,
                (id_recepcion, id_detalle, cantidad),
            )
            cursor.execute(
                """
                UPDATE detalles_orden
                SET cantidad_recibida = cantidad_recibida + %s
                WHERE id_detalle = %s
                """,
                (cantidad, id_detalle),
            )

            detalle["cantidad_recibida"] = detalle["cantidad_recibida"] + cantidad
            items_evento.append(
                {
                    "sku": detalle["sku"],
                    "cantidad": cantidad,
                    "costo_unitario": detalle["precio_unitario"],
                }
            )
            items_respuesta.append(
                {
                    "id_detalle": id_detalle,
                    "sku": detalle["sku"],
                    "cantidad": cantidad,
                    "precio_unitario": detalle["precio_unitario"],
                }
            )

        recibida_completa = all(
            det["cantidad_recibida"] >= det["cantidad_pedida"] for det in detalles
        )
        nuevo_estado = "RECIBIDA" if recibida_completa else "RECIBIDA_PARCIAL"

        cursor.execute(
            """
            UPDATE ordenes_compra
            SET estado = %s,
                actualizada_en = UTC_TIMESTAMP()
            WHERE id_orden = %s
            """,
            (nuevo_estado, id_orden),
        )

        publicar_mercancia_recibida(
            id_orden=id_orden,
            id_recepcion=id_recepcion,
            id_bodega=orden["id_bodega_destino"],
            id_usuario=id_usuario,
            items=items_evento,
        )
        publicar_orden_actualizada(
            id_orden=id_orden,
            numero=orden["numero"],
            id_proveedor=orden["id_proveedor"],
            estado=nuevo_estado,
            total=orden["total"],
        )

        cursor.execute(
            """
            SELECT id_recepcion, id_orden, fecha, id_usuario, observaciones
            FROM recepciones
            WHERE id_recepcion = %s
            """,
            (id_recepcion,),
        )
        recepcion = cursor.fetchone()
        recepcion["estado_orden"] = nuevo_estado
        recepcion["items"] = items_respuesta
        return recepcion


def listar_recepciones_por_orden(id_orden: int) -> list[dict[str, Any]]:
    """Lista las recepciones registradas para una orden con sus items."""
    with obtener_conexion() as (_conn, cursor):
        _obtener_orden_base(cursor, id_orden)

        cursor.execute(
            """
            SELECT id_recepcion, id_orden, fecha, id_usuario, observaciones
            FROM recepciones
            WHERE id_orden = %s
            ORDER BY fecha DESC, id_recepcion DESC
            """,
            (id_orden,),
        )
        recepciones = list(cursor.fetchall())
        if not recepciones:
            return []

        ids_recepcion = [rec["id_recepcion"] for rec in recepciones]
        marcadores = ", ".join(["%s"] * len(ids_recepcion))
        cursor.execute(
            f"""
            SELECT
                rd.id_recepcion,
                rd.id_detalle,
                d.sku,
                rd.cantidad,
                d.precio_unitario
            FROM recepcion_detalle rd
            INNER JOIN detalles_orden d ON d.id_detalle = rd.id_detalle
            WHERE rd.id_recepcion IN ({marcadores})
            ORDER BY rd.id_recepcion ASC, rd.id_detalle ASC
            """,
            tuple(ids_recepcion),
        )
        items_por_rec: dict[int, list[dict[str, Any]]] = {rid: [] for rid in ids_recepcion}
        for fila in cursor.fetchall():
            rid = fila.pop("id_recepcion")
            items_por_rec.setdefault(rid, []).append(fila)

        for recepcion in recepciones:
            recepcion["items"] = items_por_rec.get(recepcion["id_recepcion"], [])

        return recepciones
