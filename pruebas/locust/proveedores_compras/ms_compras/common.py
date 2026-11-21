"""Utilidades compartidas para las pruebas de rendimiento Locust de MS-Compras (P08-P15).

Centraliza configuracion por variables de entorno, construccion de cabeceras de
autenticacion interna, generadores de payloads validos sin colisiones, helpers
de validacion de respuestas JSON y la clase base LoadTestShape para pruebas de
estres progresivo.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import itertools
import os
import random
from typing import Any
import uuid

from locust import LoadTestShape, between
import requests

HOST_DEFECTO = os.getenv("HOST") or os.getenv("LT_HOST") or "http://127.0.0.1:5004"
SERVICE_TOKEN = (
    os.getenv("SERVICE_TOKEN")
    or os.getenv("LT_SERVICE_TOKEN")
    or "token-servicio-inventarios-2026-vm"
)
USER_ID_DEFECTO = int(os.getenv("LT_USER_ID", "1"))
USER_ROLE_DEFECTO = os.getenv("LT_USER_ROLE", "admin")

ESTADOS_VALIDOS = ("BORRADOR", "APROBADA", "RECIBIDA_PARCIAL", "RECIBIDA", "ANULADA")
SKUS_CATALOGO = (
    "LAC-0001",
    "LAC-0004",
    "CAR-0001",
    "BEB-0001",
    "BEB-0002",
    "BEB-0005",
    "GRA-0001",
    "ASE-0001",
    "PAN-0001",
    "FRU-0001",
)

_CONTADOR_SKU = itertools.count(1)


def _parsear_enteros_csv(valor: str, defecto: tuple[int, ...]) -> tuple[int, ...]:
    elementos: list[int] = []
    for parte in valor.split(","):
        limpio = parte.strip()
        if limpio.isdigit() and int(limpio) > 0:
            elementos.append(int(limpio))
    return tuple(elementos) if elementos else defecto


PROVEEDOR_IDS = _parsear_enteros_csv(os.getenv("LT_PROVEEDOR_IDS", "1,2,3,4"), (1, 2, 3, 4))
BODEGA_IDS = _parsear_enteros_csv(os.getenv("LT_BODEGA_IDS", "1,2,3"), (1, 2, 3))


def pausa_configurada(min_defecto: float = 1.0, max_defecto: float = 3.0):
    """Devuelve wait_time parametrizable via LT_PAUSA_MIN y LT_PAUSA_MAX."""
    pausa_min = float(os.getenv("LT_PAUSA_MIN", str(min_defecto)))
    pausa_max = float(os.getenv("LT_PAUSA_MAX", str(max_defecto)))
    if pausa_max < pausa_min:
        pausa_max = pausa_min
    return between(pausa_min, pausa_max)


def construir_cabeceras(
    rol: str | None = None,
    user_id: int | None = None,
    token: str | None = None,
    incluir_auth: bool = True,
) -> dict[str, str]:
    """Construye cabeceras internas requeridas por MS-Compras/app/auth.py.

    MS-Compras valida Authorization: Bearer <SERVICE_TOKEN>, X-User-Id y
    X-User-Role; tambien adjunta X-Service-Token y X-Correlation-Id unico.
    """
    tok = SERVICE_TOKEN if token is None else token
    uid = USER_ID_DEFECTO if user_id is None else user_id
    rol_efectivo = USER_ROLE_DEFECTO if rol is None else rol

    headers: dict[str, str] = {
        "Accept": "application/json",
        "X-User-Id": str(uid),
        "X-User-Role": rol_efectivo,
        "X-Correlation-Id": f"lt-compras-{uuid.uuid4()}",
    }
    if incluir_auth:
        headers["Authorization"] = f"Bearer {tok}"
        headers["X-Service-Token"] = tok
    return headers


def rango_fechas_reciente(dias: int = 30) -> tuple[str, str]:
    """Devuelve rango (desde, hasta) en formato YYYY-MM-DD UTC."""
    hoy = datetime.now(timezone.utc).date()
    inicio = hoy - timedelta(days=dias)
    return inicio.isoformat(), hoy.isoformat()


def generar_payload_orden(num_items: int = 2, cantidad: str = "10.000") -> dict[str, Any]:
    """Genera payload valido para POST/PUT /ordenes-compra sin SKUs duplicados."""
    items: list[dict[str, Any]] = []
    for _ in range(max(1, num_items)):
        seq = next(_CONTADOR_SKU)
        sku = f"LT-OC-{seq:07d}"
        precio = f"{random.randint(1500, 25000)}.00"
        items.append(
            {
                "sku": sku,
                "cantidad": cantidad,
                "precio_unitario": precio,
            }
        )
    return {
        "id_proveedor": random.choice(PROVEEDOR_IDS),
        "id_bodega_destino": random.choice(BODEGA_IDS),
        "items": items,
    }


def descubrir_ordenes_base(host: str, timeout: float = 10.0) -> dict[str, Any]:
    """Verifica conectividad con MS-Compras y descubre IDs existentes por estado."""
    base = host.rstrip("/")
    try:
        resp_health = requests.get(f"{base}/health", timeout=timeout)
    except requests.RequestException as exc:
        raise SystemExit(
            f"[ms-compras] No se pudo conectar con {base}/health: {exc}. "
            "Verifique que MS-Compras este levantado (cd MS-Compras && docker compose up -d)."
        ) from exc

    if resp_health.status_code != 200:
        raise SystemExit(
            f"[ms-compras] /health respondio HTTP {resp_health.status_code} en {base}."
        )

    resp_list = requests.get(
        f"{base}/ordenes-compra",
        params={"page": 1, "per_page": 100},
        headers=construir_cabeceras(rol="admin"),
        timeout=timeout,
    )
    if resp_list.status_code != 200:
        raise SystemExit(
            f"[ms-compras] GET /ordenes-compra fallo en arranque (HTTP {resp_list.status_code}): "
            f"{resp_list.text[:200]}. Verifique SERVICE_TOKEN."
        )

    cuerpo = resp_list.json()
    ordenes = cuerpo.get("data", [])
    ids_todos: list[int] = []
    por_estado: dict[str, list[int]] = {estado: [] for estado in ESTADOS_VALIDOS}

    for orden in ordenes:
        oid = orden.get("id_orden")
        est = orden.get("estado")
        if isinstance(oid, int):
            ids_todos.append(oid)
            if est in por_estado:
                por_estado[est].append(oid)

    if not ids_todos:
        ids_todos = [1, 2, 3, 4, 5]

    return {
        "ids": ids_todos,
        "por_estado": por_estado,
    }


def verificar_readiness_integrado(host: str, timeout: float = 10.0) -> None:
    """Verifica /health/ready (MySQL + RabbitMQ) antes de pruebas integradas."""
    base = host.rstrip("/")
    try:
        resp = requests.get(f"{base}/health/ready", timeout=timeout)
    except requests.RequestException as exc:
        raise SystemExit(
            f"[ms-compras] Error consultando {base}/health/ready: {exc}"
        ) from exc

    if resp.status_code != 200:
        raise SystemExit(
            f"[ms-compras] /health/ready respondio HTTP {resp.status_code} ({resp.text[:250]}). "
            "Las pruebas integradas (P11, P12, P14) requieren RabbitMQ activo en la red redapi "
            "(cd infra/rabbitmq && docker compose up -d) y MS-Proveedores accesible "
            "(o mock_proveedores.py)."
        )


def validar_listado_paginado(response: Any, clave_items: str = "data") -> dict[str, Any] | None:
    """Valida respuesta 200 con estructura {data: list, meta: {page, per_page, total, total_pages}}."""
    if response.status_code != 200:
        response.failure(f"HTTP inesperado {response.status_code}: {response.text[:160]}")
        return None
    try:
        cuerpo = response.json()
    except ValueError:
        response.failure("Respuesta no es JSON valido")
        return None

    if not isinstance(cuerpo, dict):
        response.failure("Cuerpo JSON no es un objeto")
        return None
    if not isinstance(cuerpo.get(clave_items), list):
        response.failure(f"Campo '{clave_items}' ausente o no es lista")
        return None
    meta = cuerpo.get("meta")
    if not isinstance(meta, dict) or not {"page", "per_page", "total", "total_pages"} <= set(meta):
        response.failure("Objeto 'meta' de paginacion incompleto")
        return None

    response.success()
    return cuerpo


def validar_orden_objeto(
    response: Any,
    status_esperado: int = 200,
    estado_esperado: str | None = None,
) -> dict[str, Any] | None:
    """Valida respuesta de orden individual con campos obligatorios."""
    if response.status_code != status_esperado:
        response.failure(
            f"Se esperaba HTTP {status_esperado}, llego {response.status_code}: {response.text[:160]}"
        )
        return None
    try:
        cuerpo = response.json()
    except ValueError:
        response.failure("Respuesta de orden no es JSON valido")
        return None

    if not isinstance(cuerpo, dict) or "id_orden" not in cuerpo or "estado" not in cuerpo:
        response.failure("Estructura de orden invalida (faltan id_orden o estado)")
        return None
    if estado_esperado and cuerpo.get("estado") != estado_esperado:
        response.failure(
            f"Estado esperado {estado_esperado}, recibido {cuerpo.get('estado')}"
        )
        return None

    response.success()
    return cuerpo


def validar_error_esperado(
    response: Any,
    status_esperado: int,
    codigo_esperado: str | None = None,
) -> None:
    """Valida que una peticion negativa retorne el codigo HTTP y error JSON esperados."""
    if response.status_code != status_esperado:
        response.failure(
            f"Se esperaba HTTP {status_esperado}, recibido {response.status_code}: {response.text[:160]}"
        )
        return
    try:
        cuerpo = response.json()
    except ValueError:
        response.failure("Respuesta de error no es JSON valido")
        return

    error_obj = cuerpo.get("error") if isinstance(cuerpo, dict) else None
    codigo = error_obj.get("codigo") if isinstance(error_obj, dict) else cuerpo.get("codigo")
    if codigo_esperado and codigo != codigo_esperado:
        response.failure(
            f"Codigo de error esperado {codigo_esperado}, recibido {codigo!r}"
        )
        return

    response.success()


class FormaEstresEscalonada(LoadTestShape):
    """Rampa escalonada progresiva para pruebas de estres segun locust_test.pdf.

    Incrementa usuarios por escalon hasta alcanzar max_usuarios o detectar punto
    de quiebre cuando fail_ratio supera limite_errores (tras un minimo de
    peticiones para evitar cortes prematuros por ruido inicial).
    """

    paso_usuarios: int = 20
    paso_segundos: int = 30
    max_usuarios: int = 200
    limite_errores: float = 0.05
    min_peticiones_corte: int = 20

    def tick(self) -> tuple[int, float] | None:
        tiempo = self.get_run_time()
        total_reqs = self.runner.stats.total.num_requests
        if total_reqs >= self.min_peticiones_corte:
            if self.runner.stats.total.fail_ratio > self.limite_errores:
                return None

        escalon = int(tiempo // self.paso_segundos) + 1
        usuarios = escalon * self.paso_usuarios
        if usuarios > self.max_usuarios:
            return None

        return usuarios, float(self.paso_usuarios)
