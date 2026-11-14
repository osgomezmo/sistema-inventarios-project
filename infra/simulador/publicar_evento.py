#!/usr/bin/env python3
"""Herramienta CLI para publicar eventos de prueba en RabbitMQ (inventario.eventos).

Construye el sobre JSON estandarizado de la arquitectura:
  - id_evento (UUID v4 o fijado para pruebas de idempotencia)
  - tipo (Nombre del evento / Routing key)
  - fecha (ISO 8601 UTC terminada en Z)
  - productor (Microservicio emisor)
  - id_correlacion (UUID v4 de trazabilidad)
  - datos (Payload de la entidad)
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import uuid

try:
    from dotenv import load_dotenv

    # Intenta cargar variables desde infra/rabbitmq/.env si existe
    env_rabbitmq = Path(__file__).resolve().parent.parent / "rabbitmq" / ".env"
    if env_rabbitmq.exists():
        load_dotenv(env_rabbitmq)
    else:
        load_dotenv()
except ImportError:
    pass

import pika

DEFAULT_HOST = os.getenv("RABBITMQ_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
DEFAULT_USER = os.getenv("RABBITMQ_USER") or os.getenv("RABBITMQ_DEFAULT_USER", "inventario")
DEFAULT_PASS = os.getenv("RABBITMQ_PASS") or os.getenv("RABBITMQ_DEFAULT_PASS", "inventario_secret")
DEFAULT_VHOST = os.getenv("RABBITMQ_VHOST", "/")
DEFAULT_EXCHANGE = os.getenv("RABBITMQ_EXCHANGE", "inventario.eventos")


def fecha_utc_actual() -> str:
    """Devuelve la fecha actual en formato ISO 8601 UTC terminada en Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def construir_sobre(
    tipo: str,
    productor: str,
    datos: dict,
    id_evento: str | None = None,
    id_correlacion: str | None = None,
) -> dict:
    """Construye el sobre estándar de eventos de inventario."""
    return {
        "id_evento": id_evento or str(uuid.uuid4()),
        "tipo": tipo,
        "fecha": fecha_utc_actual(),
        "productor": productor,
        "id_correlacion": id_correlacion or str(uuid.uuid4()),
        "datos": datos,
    }


def publicar_en_rabbitmq(
    sobre: dict,
    routing_key: str,
    host: str,
    port: int,
    user: str,
    password: str,
    vhost: str,
    exchange: str,
):
    """Publica el sobre serializado en JSON en el exchange especificado con delivery_mode=2."""
    credenciales = pika.PlainCredentials(user, password)
    parametros = pika.ConnectionParameters(
        host=host,
        port=port,
        virtual_host=vhost,
        credentials=credenciales,
        connection_attempts=3,
        retry_delay=2,
    )

    cuerpo = json.dumps(sobre, ensure_ascii=False, indent=2)

    try:
        conexion = pika.BlockingConnection(parametros)
        canal = conexion.channel()

        propiedades = pika.BasicProperties(
            content_type="application/json",
            content_encoding="utf-8",
            delivery_mode=2,  # Mensaje persistente en disco
            message_id=sobre["id_evento"],
            correlation_id=sobre["id_correlacion"],
            timestamp=int(datetime.now(timezone.utc).timestamp()),
            headers={"productor": sobre["productor"]},
        )

        canal.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=cuerpo,
            properties=propiedades,
        )

        conexion.close()
        print("=" * 70)
        print("  EVENTO PUBLICADO EXITOSAMENTE")
        print("=" * 70)
        print(f"  Exchange:       {exchange}")
        print(f"  Routing Key:    {routing_key}")
        print(f"  ID Evento:      {sobre['id_evento']}")
        print(f"  Correlación:    {sobre['id_correlacion']}")
        print(f"  Productor:      {sobre['productor']}")
        print(f"  Delivery Mode:  2 (Persistent)")
        print("-" * 70)
        print("  Cuerpo del mensaje:")
        print(cuerpo)
        print("=" * 70)
    except pika.exceptions.AMQPConnectionError as err:
        print(
            f"\n[ERROR DE CONEXION] No se pudo conectar a RabbitMQ en {host}:{port} vhost '{vhost}'.",
            file=sys.stderr,
        )
        print(f"Detalle técnico: {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(f"\n[ERROR AL PUBLICAR] {err}", file=sys.stderr)
        sys.exit(1)


def main():
    # Parser padre para opciones transversales de conexión y sobre
    comun = argparse.ArgumentParser(add_help=False)
    comun.add_argument(
        "--id-evento",
        dest="id_evento",
        default=None,
        help="UUID v4 explícito para el evento (útil para probar idempotencia). Si no se pasa, se genera uno nuevo.",
    )
    comun.add_argument(
        "--id-correlacion",
        dest="id_correlacion",
        default=None,
        help="UUID v4 de correlación (X-Correlation-Id). Si no se pasa, se genera uno nuevo.",
    )
    comun.add_argument(
        "--productor",
        dest="productor",
        default=None,
        help="Nombre del microservicio emisor (por defecto según la plantilla del evento).",
    )
    comun.add_argument(
        "--corrupto",
        action="store_true",
        help="Genera un payload incompleto/inválido para forzar rechazo en el consumidor y verificar la Dead Letter Queue.",
    )
    comun.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Host de RabbitMQ (def: {DEFAULT_HOST}).",
    )
    comun.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Puerto AMQP de RabbitMQ (def: {DEFAULT_PORT}).",
    )
    comun.add_argument(
        "--user",
        default=DEFAULT_USER,
        help=f"Usuario de RabbitMQ (def: {DEFAULT_USER}).",
    )
    comun.add_argument(
        "--password",
        default=DEFAULT_PASS,
        help="Contraseña de RabbitMQ.",
    )
    comun.add_argument(
        "--vhost",
        default=DEFAULT_VHOST,
        help=f"Virtual host de RabbitMQ (def: {DEFAULT_VHOST}).",
    )
    comun.add_argument(
        "--exchange",
        default=DEFAULT_EXCHANGE,
        help=f"Nombre del exchange (def: {DEFAULT_EXCHANGE}).",
    )

    parser = argparse.ArgumentParser(
        prog="publicar_evento.py",
        description="Publicador CLI de eventos de prueba para RabbitMQ (Sistema de Inventarios).",
    )

    subparsers = parser.add_subparsers(
        dest="evento",
        required=True,
        help="Tipo de evento a publicar",
    )

    # 1. Plantilla StockBajoUmbral
    p_stock = subparsers.add_parser(
        "StockBajoUmbral",
        parents=[comun],
        help="Publica evento de alerta cuando el saldo de un producto cae al mínimo o debajo.",
    )
    p_stock.add_argument("--sku", default="LAC-0001", help="SKU del producto (def: LAC-0001).")
    p_stock.add_argument(
        "--bodega",
        type=int,
        default=1,
        help="Identificador de la bodega (def: 1).",
    )
    p_stock.add_argument(
        "--saldo",
        type=float,
        default=4.0,
        help="Saldo resultante en bodega (def: 4.0).",
    )
    p_stock.add_argument(
        "--minimo",
        type=float,
        default=10.0,
        help="Stock mínimo configurado para el producto (def: 10.0).",
    )

    # 2. Plantilla MovimientoRegistrado
    p_mov = subparsers.add_parser(
        "MovimientoRegistrado",
        parents=[comun],
        help="Publica evento por cada entrada, salida, ajuste o traslado en inventario.",
    )
    p_mov.add_argument(
        "--id-movimiento",
        type=int,
        default=101,
        help="Identificador único del movimiento (def: 101).",
    )
    p_mov.add_argument("--sku", default="LAC-0001", help="SKU del producto (def: LAC-0001).")
    p_mov.add_argument(
        "--bodega",
        type=int,
        default=1,
        help="Identificador de la bodega (def: 1).",
    )
    p_mov.add_argument(
        "--tipo",
        default="SALIDA",
        help="Tipo de movimiento (ENTRADA_COMPRA, SALIDA, AJUSTE_POSITIVO, etc., def: SALIDA).",
    )
    p_mov.add_argument(
        "--cantidad",
        type=float,
        default=2.0,
        help="Cantidad involucrada en el movimiento (def: 2.0).",
    )
    p_mov.add_argument(
        "--costo-unitario",
        type=float,
        default=3150.0,
        help="Costo unitario del movimiento (def: 3150.0).",
    )
    p_mov.add_argument(
        "--saldo-resultante",
        type=float,
        default=4.0,
        help="Saldo resultante tras la operación (def: 4.0).",
    )
    p_mov.add_argument(
        "--costo-promedio",
        type=float,
        default=3150.0,
        help="Costo promedio ponderado resultante (def: 3150.0).",
    )
    p_mov.add_argument(
        "--valor-resultante",
        type=float,
        default=12600.0,
        help="Valorización resultante en inventario (def: 12600.0).",
    )

    # 3. Plantilla OrdenCompraActualizada
    p_orden = subparsers.add_parser(
        "OrdenCompraActualizada",
        parents=[comun],
        help="Publica evento cada vez que una orden de compra cambia de estado.",
    )
    p_orden.add_argument(
        "--id-orden",
        type=int,
        default=15,
        help="Identificador de la orden de compra (def: 15).",
    )
    p_orden.add_argument(
        "--numero",
        default="OC-0015",
        help="Código o número visible de la orden (def: OC-0015).",
    )
    p_orden.add_argument(
        "--proveedor",
        type=int,
        default=3,
        help="Identificador del proveedor (def: 3).",
    )
    p_orden.add_argument(
        "--estado",
        default="APROBADA",
        help="Estado de la orden (BORRADOR, APROBADA, RECIBIDA_PARCIAL, RECIBIDA, ANULADA, def: APROBADA).",
    )
    p_orden.add_argument(
        "--total",
        type=float,
        default=450000.0,
        help="Total monetario de la orden (def: 450000.0).",
    )

    # 4. Plantilla MercanciaRecibida (adicional de apoyo)
    p_rec = subparsers.add_parser(
        "MercanciaRecibida",
        parents=[comun],
        help="Publica evento al recepcionar mercadería de una orden de compra.",
    )
    p_rec.add_argument("--id-orden", type=int, default=15, help="ID de la orden (def: 15).")
    p_rec.add_argument("--id-recepcion", type=int, default=1, help="ID de recepción (def: 1).")
    p_rec.add_argument("--bodega", type=int, default=1, help="ID de bodega (def: 1).")
    p_rec.add_argument("--usuario", type=int, default=1, help="ID del usuario receptor (def: 1).")
    p_rec.add_argument("--sku", default="LAC-0001", help="SKU del ítem (def: LAC-0001).")
    p_rec.add_argument("--cantidad", type=float, default=10.0, help="Cantidad (def: 10.0).")
    p_rec.add_argument("--costo", type=float, default=3000.0, help="Costo unitario (def: 3000.0).")

    # 5. Plantilla DevolucionProveedorRegistrada (adicional de apoyo)
    p_dev = subparsers.add_parser(
        "DevolucionProveedorRegistrada",
        parents=[comun],
        help="Publica evento al registrar una devolución a proveedor.",
    )
    p_dev.add_argument("--id-orden", type=int, default=15, help="ID de la orden (def: 15).")
    p_dev.add_argument("--id-devolucion", type=int, default=1, help="ID de devolución (def: 1).")
    p_dev.add_argument("--bodega", type=int, default=1, help="ID de bodega (def: 1).")
    p_dev.add_argument("--usuario", type=int, default=1, help="ID del usuario (def: 1).")
    p_dev.add_argument("--motivo", default="Producto defectuoso", help="Motivo de devolución.")
    p_dev.add_argument("--sku", default="LAC-0001", help="SKU devuelto (def: LAC-0001).")
    p_dev.add_argument("--cantidad", type=float, default=2.0, help="Cantidad devuelta (def: 2.0).")

    # 6. Modo Genérico / Personalizado
    p_custom = subparsers.add_parser(
        "Personalizado",
        parents=[comun],
        help="Publica un evento con tipo y payload JSON arbitrarios.",
    )
    p_custom.add_argument(
        "--tipo-evento",
        required=True,
        help="Nombre del evento y routing key.",
    )
    p_custom.add_argument(
        "--datos-json",
        default="{}",
        help="String JSON con el objeto de datos.",
    )

    args = parser.parse_args()

    tipo_evento = args.evento
    productor_defecto = "ms-inventario"
    datos = {}

    if tipo_evento == "StockBajoUmbral":
        productor_defecto = "ms-inventario"
        if args.corrupto:
            print("[AVISO] Generando payload CORRUPTO/INCOMPLETO para StockBajoUmbral.")
            datos = {"id_bodega": args.bodega}  # Omite sku, saldo y stock_minimo
        else:
            datos = {
                "sku": args.sku,
                "id_bodega": args.bodega,
                "saldo": args.saldo,
                "stock_minimo": args.minimo,
            }

    elif tipo_evento == "MovimientoRegistrado":
        productor_defecto = "ms-inventario"
        if args.corrupto:
            print("[AVISO] Generando payload CORRUPTO/INCOMPLETO para MovimientoRegistrado.")
            datos = {
                "id_movimiento": args.id_movimiento,
                "tipo": "TIPO_INVALIDO",
            }  # Omite sku, cantidad, bodegas, costos
        else:
            datos = {
                "id_movimiento": args.id_movimiento,
                "sku": args.sku,
                "id_bodega": args.bodega,
                "tipo": args.tipo,
                "cantidad": args.cantidad,
                "costo_unitario": args.costo_unitario,
                "saldo_resultante": args.saldo_resultante,
                "costo_promedio": args.costo_promedio,
                "valor_resultante": args.valor_resultante,
            }

    elif tipo_evento == "OrdenCompraActualizada":
        productor_defecto = "ms-compras"
        if args.corrupto:
            print("[AVISO] Generando payload CORRUPTO/INCOMPLETO para OrdenCompraActualizada.")
            datos = {"id_orden": args.id_orden}  # Omite estado, numero, total
        else:
            datos = {
                "id_orden": args.id_orden,
                "numero": args.numero,
                "id_proveedor": args.proveedor,
                "estado": args.estado,
                "total": args.total,
            }

    elif tipo_evento == "MercanciaRecibida":
        productor_defecto = "ms-compras"
        if args.corrupto:
            print("[AVISO] Generando payload CORRUPTO/INCOMPLETO para MercanciaRecibida.")
            datos = {"id_orden": args.id_orden}
        else:
            datos = {
                "id_orden": args.id_orden,
                "id_recepcion": args.id_recepcion,
                "id_bodega": args.bodega,
                "id_usuario": args.usuario,
                "items": [
                    {
                        "sku": args.sku,
                        "cantidad": args.cantidad,
                        "costo_unitario": args.costo,
                    }
                ],
            }

    elif tipo_evento == "DevolucionProveedorRegistrada":
        productor_defecto = "ms-compras"
        if args.corrupto:
            print("[AVISO] Generando payload CORRUPTO/INCOMPLETO para DevolucionProveedorRegistrada.")
            datos = {"id_orden": args.id_orden}
        else:
            datos = {
                "id_orden": args.id_orden,
                "id_devolucion": args.id_devolucion,
                "id_bodega": args.bodega,
                "id_usuario": args.usuario,
                "motivo": args.motivo,
                "items": [
                    {
                        "sku": args.sku,
                        "cantidad": args.cantidad,
                    }
                ],
            }

    elif tipo_evento == "Personalizado":
        tipo_evento = args.tipo_evento
        productor_defecto = "ms-simulador"
        try:
            datos = json.loads(args.datos_json)
        except json.JSONDecodeError as err:
            print(f"[ERROR] El parámetro --datos-json no es un JSON válido: {err}", file=sys.stderr)
            sys.exit(1)

    productor = args.productor or productor_defecto

    sobre = construir_sobre(
        tipo=tipo_evento,
        productor=productor,
        datos=datos,
        id_evento=args.id_evento,
        id_correlacion=args.id_correlacion,
    )

    publicar_en_rabbitmq(
        sobre=sobre,
        routing_key=tipo_evento,
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        vhost=args.vhost,
        exchange=args.exchange,
    )


if __name__ == "__main__":
    main()
