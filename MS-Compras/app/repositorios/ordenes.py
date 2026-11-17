"""Operaciones de persistencia y transiciones de ordenes de compra."""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.clientes.proveedores import validar_proveedor_activo
from app.db import obtener_conexion, transaccion
from app.errors import ErrorAPI
from app.messaging.publicador import publicar_orden_actualizada


def _calcular_total(items: list[dict[str, Any]]) -> Decimal:
    """Calcula el total monetario exacto de una orden usando Decimal."""
    total = sum(
        (item["cantidad_pedida"] * item["precio_unitario"] for item in items),
        Decimal("0.00"),
    )
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _obtener_orden_base(cursor: Any, id_orden: int, bloquear: bool = False) -> dict[str, Any]:
    """Obtiene la fila de ordenes_compra o lanza 404 si no existe."""
    clausula_lock = " FOR UPDATE" if bloquear else ""
    cursor.execute(
        f"""
        SELECT
            id_orden,
            numero,
            id_proveedor,
            id_bodega_destino,
            estado,
            total,
            id_usuario_creador,
            id_usuario_aprobador,
            motivo_anulacion,
            creada_en,
            aprobada_en,
            actualizada_en
        FROM ordenes_compra
        WHERE id_orden = %s
        {clausula_lock}
        """,
        (id_orden,),
    )
    orden = cursor.fetchone()
    if not orden:
        raise ErrorAPI(
            404,
            "NO_EXISTE",
            f"La orden de compra {id_orden} no existe.",
            {"id_orden": id_orden},
        )
    return orden


def _obtener_detalles_orden(cursor: Any, id_orden: int, bloquear: bool = False) -> list[dict[str, Any]]:
    """Lista los renglones de detalles_orden asociados a una orden."""
    clausula_lock = " FOR UPDATE" if bloquear else ""
    cursor.execute(
        f"""
        SELECT
            id_detalle,
            id_orden,
            sku,
            cantidad_pedida,
            cantidad_recibida,
            cantidad_devuelta,
            precio_unitario
        FROM detalles_orden
        WHERE id_orden = %s
        ORDER BY id_detalle ASC
        {clausula_lock}
        """,
        (id_orden,),
    )
    return list(cursor.fetchall())


def _cargar_detalles_por_orden_ids(
    cursor: Any,
    ids_orden: list[int],
) -> dict[int, list[dict[str, Any]]]:
    """Carga en lote los detalles de varias ordenes para evitar consultas N+1."""
    if not ids_orden:
        return {}
    marcadores = ", ".join(["%s"] * len(ids_orden))
    cursor.execute(
        f"""
        SELECT
            id_detalle,
            id_orden,
            sku,
            cantidad_pedida,
            cantidad_recibida,
            cantidad_devuelta,
            precio_unitario
        FROM detalles_orden
        WHERE id_orden IN ({marcadores})
        ORDER BY id_orden ASC, id_detalle ASC
        """,
        tuple(ids_orden),
    )
    agrupados: dict[int, list[dict[str, Any]]] = {id_ord: [] for id_ord in ids_orden}
    for fila in cursor.fetchall():
        agrupados.setdefault(fila["id_orden"], []).append(fila)
    return agrupados


def _armar_orden_completa(cursor: Any, orden: dict[str, Any]) -> dict[str, Any]:
    """Adjunta items, recepciones (con sus items) y devoluciones (con sus items)."""
    id_orden = orden["id_orden"]
    orden["items"] = _obtener_detalles_orden(cursor, id_orden)

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
    if recepciones:
        ids_rec = [rec["id_recepcion"] for rec in recepciones]
        marcadores_rec = ", ".join(["%s"] * len(ids_rec))
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
            WHERE rd.id_recepcion IN ({marcadores_rec})
            ORDER BY rd.id_recepcion ASC, rd.id_detalle ASC
            """,
            tuple(ids_rec),
        )
        items_por_rec: dict[int, list[dict[str, Any]]] = {rid: [] for rid in ids_rec}
        for fila in cursor.fetchall():
            rid = fila.pop("id_recepcion")
            items_por_rec.setdefault(rid, []).append(fila)
        for rec in recepciones:
            rec["items"] = items_por_rec.get(rec["id_recepcion"], [])
    orden["recepciones"] = recepciones

    cursor.execute(
        """
        SELECT id_devolucion, id_orden, fecha, motivo, id_usuario
        FROM devoluciones_proveedor
        WHERE id_orden = %s
        ORDER BY fecha DESC, id_devolucion DESC
        """,
        (id_orden,),
    )
    devoluciones = list(cursor.fetchall())
    if devoluciones:
        ids_dev = [dev["id_devolucion"] for dev in devoluciones]
        marcadores_dev = ", ".join(["%s"] * len(ids_dev))
        cursor.execute(
            f"""
            SELECT
                dd.id_devolucion,
                dd.id_detalle,
                d.sku,
                dd.cantidad
            FROM devolucion_detalle dd
            INNER JOIN detalles_orden d ON d.id_detalle = dd.id_detalle
            WHERE dd.id_devolucion IN ({marcadores_dev})
            ORDER BY dd.id_devolucion ASC, dd.id_detalle ASC
            """,
            tuple(ids_dev),
        )
        items_por_dev: dict[int, list[dict[str, Any]]] = {did: [] for did in ids_dev}
        for fila in cursor.fetchall():
            did = fila.pop("id_devolucion")
            items_por_dev.setdefault(did, []).append(fila)
        for dev in devoluciones:
            dev["items"] = items_por_dev.get(dev["id_devolucion"], [])
    orden["devoluciones"] = devoluciones
    return orden


def listar_ordenes(
    estado: str | None,
    id_proveedor: int | None,
    desde: datetime | None,
    hasta: datetime | None,
    limite: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    """Lista ordenes de compra filtradas y paginadas."""
    condiciones: list[str] = []
    parametros: list[Any] = []

    if estado:
        condiciones.append("estado = %s")
        parametros.append(estado)
    if id_proveedor is not None:
        condiciones.append("id_proveedor = %s")
        parametros.append(id_proveedor)
    if desde is not None:
        condiciones.append("creada_en >= %s")
        parametros.append(desde)
    if hasta is not None:
        condiciones.append("creada_en <= %s")
        parametros.append(hasta)

    where_sql = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""

    with obtener_conexion() as (_conn, cursor):
        cursor.execute(
            f"SELECT COUNT(*) AS total FROM ordenes_compra {where_sql}",
            tuple(parametros),
        )
        total = int(cursor.fetchone()["total"])

        cursor.execute(
            f"""
            SELECT
                id_orden,
                numero,
                id_proveedor,
                id_bodega_destino,
                estado,
                total,
                id_usuario_creador,
                id_usuario_aprobador,
                motivo_anulacion,
                creada_en,
                aprobada_en,
                actualizada_en
            FROM ordenes_compra
            {where_sql}
            ORDER BY creada_en DESC, id_orden DESC
            LIMIT %s OFFSET %s
            """,
            tuple([*parametros, limite, offset]),
        )
        ordenes = list(cursor.fetchall())
        detalles_map = _cargar_detalles_por_orden_ids(
            cursor, [ord_row["id_orden"] for ord_row in ordenes]
        )
        for orden in ordenes:
            orden["items"] = detalles_map.get(orden["id_orden"], [])

    return ordenes, total


def obtener_orden_por_id(id_orden: int) -> dict[str, Any]:
    """Retorna el detalle completo de una orden de compra por ID."""
    with obtener_conexion() as (_conn, cursor):
        orden = _obtener_orden_base(cursor, id_orden)
        return _armar_orden_completa(cursor, orden)


def crear_orden_compra(payload: dict[str, Any], id_usuario: int) -> dict[str, Any]:
    """Valida proveedor, crea orden en estado BORRADOR y publica OrdenCompraActualizada."""
    validar_proveedor_activo(payload["id_proveedor"])
    total = _calcular_total(payload["items"])

    with transaccion() as (_conn, cursor):
        cursor.execute(
            """
            INSERT INTO ordenes_compra (
                numero,
                id_proveedor,
                id_bodega_destino,
                estado,
                total,
                id_usuario_creador
            ) VALUES (%s, %s, %s, 'BORRADOR', %s, %s)
            """,
            (
                None,
                payload["id_proveedor"],
                payload["id_bodega_destino"],
                total,
                id_usuario,
            ),
        )
        id_orden = int(cursor.lastrowid)
        anio = datetime.now(timezone.utc).year
        numero = f"OC-{anio}-{id_orden:06d}"

        cursor.execute(
            "UPDATE ordenes_compra SET numero = %s WHERE id_orden = %s",
            (numero, id_orden),
        )

        for item in payload["items"]:
            cursor.execute(
                """
                INSERT INTO detalles_orden (
                    id_orden,
                    sku,
                    cantidad_pedida,
                    cantidad_recibida,
                    cantidad_devuelta,
                    precio_unitario
                ) VALUES (%s, %s, %s, 0.000, 0.000, %s)
                """,
                (
                    id_orden,
                    item["sku"],
                    item["cantidad_pedida"],
                    item["precio_unitario"],
                ),
            )

        publicar_orden_actualizada(
            id_orden=id_orden,
            numero=numero,
            id_proveedor=payload["id_proveedor"],
            estado="BORRADOR",
            total=total,
        )

        orden = _obtener_orden_base(cursor, id_orden)
        return _armar_orden_completa(cursor, orden)


def actualizar_orden_borrador(id_orden: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Edita una orden de compra solo si esta en BORRADOR."""
    with obtener_conexion() as (_conn, cursor):
        orden_actual = _obtener_orden_base(cursor, id_orden)
        if orden_actual["estado"] != "BORRADOR":
            raise ErrorAPI(
                409,
                "ESTADO_NO_EDITABLE",
                "Solo las ordenes en estado BORRADOR pueden modificarse.",
                {"estado": orden_actual["estado"]},
            )

    validar_proveedor_activo(payload["id_proveedor"])
    total = _calcular_total(payload["items"])

    with transaccion() as (_conn, cursor):
        orden = _obtener_orden_base(cursor, id_orden, bloquear=True)
        if orden["estado"] != "BORRADOR":
            raise ErrorAPI(
                409,
                "ESTADO_NO_EDITABLE",
                "Solo las ordenes en estado BORRADOR pueden modificarse.",
                {"estado": orden["estado"]},
            )

        cursor.execute(
            """
            UPDATE ordenes_compra
            SET id_proveedor = %s,
                id_bodega_destino = %s,
                total = %s,
                actualizada_en = UTC_TIMESTAMP()
            WHERE id_orden = %s
            """,
            (
                payload["id_proveedor"],
                payload["id_bodega_destino"],
                total,
                id_orden,
            ),
        )

        cursor.execute("DELETE FROM detalles_orden WHERE id_orden = %s", (id_orden,))
        for item in payload["items"]:
            cursor.execute(
                """
                INSERT INTO detalles_orden (
                    id_orden,
                    sku,
                    cantidad_pedida,
                    cantidad_recibida,
                    cantidad_devuelta,
                    precio_unitario
                ) VALUES (%s, %s, %s, 0.000, 0.000, %s)
                """,
                (
                    id_orden,
                    item["sku"],
                    item["cantidad_pedida"],
                    item["precio_unitario"],
                ),
            )

        publicar_orden_actualizada(
            id_orden=id_orden,
            numero=orden["numero"] or f"OC-{datetime.now(timezone.utc).year}-{id_orden:06d}",
            id_proveedor=payload["id_proveedor"],
            estado="BORRADOR",
            total=total,
        )

        orden_actualizada = _obtener_orden_base(cursor, id_orden)
        return _armar_orden_completa(cursor, orden_actualizada)


def aprobar_orden(id_orden: int, id_usuario: int) -> dict[str, Any]:
    """Transiciona una orden BORRADOR -> APROBADA y publica OrdenCompraActualizada."""
    with transaccion() as (_conn, cursor):
        orden = _obtener_orden_base(cursor, id_orden, bloquear=True)
        if orden["estado"] != "BORRADOR":
            raise ErrorAPI(
                409,
                "TRANSICION_INVALIDA",
                f"No es posible aprobar una orden en estado {orden['estado']}.",
                {"estado_actual": orden["estado"]},
            )

        cursor.execute(
            """
            UPDATE ordenes_compra
            SET estado = 'APROBADA',
                id_usuario_aprobador = %s,
                aprobada_en = UTC_TIMESTAMP(),
                actualizada_en = UTC_TIMESTAMP()
            WHERE id_orden = %s
            """,
            (id_usuario, id_orden),
        )

        publicar_orden_actualizada(
            id_orden=id_orden,
            numero=orden["numero"],
            id_proveedor=orden["id_proveedor"],
            estado="APROBADA",
            total=orden["total"],
        )

        orden_actualizada = _obtener_orden_base(cursor, id_orden)
        return _armar_orden_completa(cursor, orden_actualizada)


def anular_orden(id_orden: int, motivo: str) -> dict[str, Any]:
    """Anula una orden en BORRADOR o APROBADA sin recepciones registradas."""
    with transaccion() as (_conn, cursor):
        orden = _obtener_orden_base(cursor, id_orden, bloquear=True)
        if orden["estado"] not in {"BORRADOR", "APROBADA"}:
            raise ErrorAPI(
                409,
                "TRANSICION_INVALIDA",
                f"No es posible anular una orden en estado {orden['estado']}.",
                {"estado_actual": orden["estado"]},
            )

        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM recepciones WHERE id_orden = %s",
            (id_orden,),
        )
        if int(cursor.fetchone()["cnt"]) > 0:
            raise ErrorAPI(
                409,
                "TRANSICION_INVALIDA",
                "No es posible anular una orden que ya tiene recepciones registradas.",
                {"id_orden": id_orden},
            )

        cursor.execute(
            """
            UPDATE ordenes_compra
            SET estado = 'ANULADA',
                motivo_anulacion = %s,
                actualizada_en = UTC_TIMESTAMP()
            WHERE id_orden = %s
            """,
            (motivo, id_orden),
        )

        publicar_orden_actualizada(
            id_orden=id_orden,
            numero=orden["numero"],
            id_proveedor=orden["id_proveedor"],
            estado="ANULADA",
            total=orden["total"],
        )

        orden_actualizada = _obtener_orden_base(cursor, id_orden)
        return _armar_orden_completa(cursor, orden_actualizada)
