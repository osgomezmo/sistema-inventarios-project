"""Utilidades compartidas para las pruebas de rendimiento de MS-Proveedores (P01..P07).

Centraliza:
- Configuracion por variables de entorno (HOST/LT_HOST, SERVICE_TOKEN/LT_SERVICE_TOKEN,
  LT_USER_ID, LT_USER_ROLE, pausas y limites de estres).
- Construccion de cabeceras de autenticacion y trazabilidad compatibles con MS-Proveedores
  (Authorization: Bearer <SERVICE_TOKEN>, X-Service-Token, X-User-Id, X-User-Role,
  X-Correlation-Id).
- Generacion segura y concurrente de NITs colombianos validos segun algoritmo DIAN
  (modulo 11 con digito de verificacion) sin colisiones 409 entre hilos ni corridas.
- Generadores de cuerpos JSON validos para proveedores, contactos y productos suministrados.
- Descubrimiento dinamico de IDs y SKUs sembrados al iniciar la prueba (test_start).
- Validadores estrictos de codigo HTTP y estructura JSON para catch_response=True.
- Fabrica de LoadTestShape para escenarios de estres progresivo (P05 y P06).
"""

from __future__ import annotations

import itertools
import logging
import os
import random
import threading
import time
import uuid
from typing import Any

import requests
from locust import LoadTestShape, events

logger = logging.getLogger("locust.ms_proveedores")

# Valores por defecto alineados con MS-Proveedores/docker-compose.yml
HOST_DEFECTO = os.getenv("LT_HOST") or os.getenv("HOST") or "http://127.0.0.1:5003"
SERVICE_TOKEN_DEFECTO = (
    os.getenv("LT_SERVICE_TOKEN")
    or os.getenv("SERVICE_TOKEN")
    or "token-servicio-inventarios-2026-vm"
)
USER_ID_DEFECTO = os.getenv("LT_USER_ID", "1")
USER_ROLE_DEFECTO = os.getenv("LT_USER_ROLE", "admin")

ROLES_LECTURA = ("admin", "jefe_bodega", "compras", "gerente")
ROLES_ESCRITURA = ("admin", "compras")

# Pesos oficiales DIAN (de derecha a izquierda) para el calculo del digito de verificacion
_PESOS_DIAN = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)

# Contador atomico y prefijo por ejecucion para garantizar NITs y SKUs unicos
_BLOQUEO_CONTADOR = threading.Lock()
_CONTADOR_NIT = itertools.count(1)
_CONTADOR_SKU = itertools.count(1)
_SEMILLA_CORRIDA = int(time.time() * 1000) % 100_000  # 5 digitos unicos por corrida
_PID_SUFIJO = os.getpid() % 100  # 2 digitos por proceso

# Catalogo de referencia (se complementa dinamicamente en test_start)
TERMINOS_BUSQUEDA = (
    "Lacteos",
    "Bebidas",
    "Abarrotes",
    "Sabana",
    "Comercializadora",
    "890",
    "900",
    "860",
)

SKUS_SEMILLA_DEFECTO = (
    "LAC-0001",
    "LAC-0002",
    "CAR-0001",
    "BEB-0001",
    "GRA-0001",
    "ASE-0001",
    "PAN-0001",
    "FRU-0001",
)

CIUDADES_COLOMBIA = (
    "Bogota",
    "Medellin",
    "Cali",
    "Barranquilla",
    "Bucaramanga",
    "Cota",
    "Funza",
    "Mosquera",
)

CARGOS_CONTACTO = (
    "Ejecutivo de cuentas clave",
    "Coordinador de despachos",
    "Jefe comercial",
    "Asesor de abastecimiento",
    "Director de logistica",
)

CONTEXTO_PROVEEDORES: dict[str, Any] = {
    "ids_activos": [1, 2, 3, 4],
    "ids_todos": [1, 2, 3, 4, 5],
    "skus_activos": list(SKUS_SEMILLA_DEFECTO),
    "inicializado": False,
}


def leer_pausa(min_defecto: float, max_defecto: float) -> tuple[float, float]:
    """Lee LT_PAUSA_MIN y LT_PAUSA_MAX con respaldo seguro por escenario."""
    pausa_min = float(os.getenv("LT_PAUSA_MIN", str(min_defecto)))
    pausa_max = float(os.getenv("LT_PAUSA_MAX", str(max_defecto)))
    if pausa_max < pausa_min:
        pausa_max = pausa_min
    return pausa_min, pausa_max


def obtener_service_token() -> str:
    """Devuelve el token de servicio vigente desde variables de entorno."""
    return (
        os.getenv("LT_SERVICE_TOKEN")
        or os.getenv("SERVICE_TOKEN")
        or SERVICE_TOKEN_DEFECTO
    )


def construir_cabeceras(
    rol: str | None = None,
    user_id: str | None = None,
    prefijo_correlacion: str = "lt-prov",
) -> dict[str, str]:
    """Construye cabeceras HTTP validas para MS-Proveedores.

    MS-Proveedores exige `Authorization: Bearer <SERVICE_TOKEN>` (src/middlewares/auth.js)
    y lee `X-User-Id`, `X-User-Role` y `X-Correlation-Id`. Adicionalmente se incluye
    `X-Service-Token` para mantener convencion uniforme con el resto de la suite.
    """
    token = obtener_service_token()
    rol_efectivo = rol or os.getenv("LT_USER_ROLE", USER_ROLE_DEFECTO)
    usuario_efectivo = user_id or os.getenv("LT_USER_ID", USER_ID_DEFECTO)
    return {
        "Authorization": f"Bearer {token}",
        "X-Service-Token": token,
        "X-User-Id": str(usuario_efectivo),
        "X-User-Role": str(rol_efectivo),
        "X-Correlation-Id": f"{prefijo_correlacion}-{uuid.uuid4()}",
        "Accept": "application/json",
    }


def calcular_dv_dian(base_numerica: str) -> int:
    """Calcula el digito de verificacion (DV) DIAN mediante modulo 11.

    Ejemplo verificado con datos semilla:
    - 890900291 -> DV 8 (890.900.291-8)
    - 860002527 -> DV 9 (860.002.527-9)
    - 900245180 -> DV 4 (900.245.180-4)
    """
    digitos = "".join(ch for ch in str(base_numerica) if ch.isdigit())
    if not digitos or len(digitos) > len(_PESOS_DIAN):
        raise ValueError(
            f"La base numerica del NIT debe tener entre 1 y {len(_PESOS_DIAN)} digitos."
        )
    acumulado = 0
    for idx, ch in enumerate(reversed(digitos)):
        acumulado += int(ch) * _PESOS_DIAN[idx]
    residuo = acumulado % 11
    return residuo if residuo in (0, 1) else 11 - residuo


def formatear_nit_dian(base_numerica: str) -> str:
    """Formatea una base numerica con separadores de miles y digito de verificacion."""
    digitos = "".join(ch for ch in str(base_numerica) if ch.isdigit())
    dv = calcular_dv_dian(digitos)
    grupos: list[str] = []
    while digitos:
        grupos.append(digitos[-3:])
        digitos = digitos[:-3]
    cuerpo = ".".join(reversed(grupos))
    return f"{cuerpo}-{dv}"


def generar_nit_dian_unico() -> str:
    """Genera un NIT colombiano valido (modulo 11 DIAN) y unico por hilo y corrida.

    Estructura de 13 digitos antes del DV (maximo 15 pesos DIAN, longitud total 19 chars,
    muy por debajo de VARCHAR(30) en la tabla `proveedores`):
    9 + SEMILLA_CORRIDA(5) + PID(2) + CONTADOR(5)
    """
    with _BLOQUEO_CONTADOR:
        sec = next(_CONTADOR_NIT) % 100_000
    base = f"9{_SEMILLA_CORRIDA:05d}{_PID_SUFIJO:02d}{sec:05d}"
    return formatear_nit_dian(base)


def generar_sku_unico(prefijo: str = "LTP") -> str:
    """Genera un SKU unico valido segun REGEX_SKU (/^[A-Za-z0-9_-]{2,50}$/)."""
    with _BLOQUEO_CONTADOR:
        sec = next(_CONTADOR_SKU)
    return f"{prefijo}-{_SEMILLA_CORRIDA:05d}-{_PID_SUFIJO:02d}-{sec:06d}"


def generar_payload_proveedor(
    etiqueta: str = "LT",
    incluir_contactos: bool = False,
    incluir_productos: bool = False,
) -> dict[str, Any]:
    """Construye un cuerpo JSON valido para POST /proveedores."""
    sufijo = uuid.uuid4().hex[:8]
    ciudad = random.choice(CIUDADES_COLOMBIA)
    cuerpo: dict[str, Any] = {
        "nit": generar_nit_dian_unico(),
        "razon_social": f"Proveedor {etiqueta} {sufijo.upper()} S.A.S.",
        "telefono": f"+57 601 {random.randint(2000000, 9999999)}",
        "email": f"compras.{sufijo}@lt-proveedores.example.co",
        "direccion": f"Calle {random.randint(10, 170)} # {random.randint(1, 99)}-{random.randint(10, 99)}, {ciudad}",
    }
    if incluir_contactos:
        cuerpo["contactos"] = [generar_payload_contacto(etiqueta)]
    if incluir_productos:
        cuerpo["productos"] = [
            {
                "sku": generar_sku_unico(f"LT{etiqueta[:2].upper()}"),
                "precio_compra": f"{random.uniform(1200.0, 48000.0):.2f}",
                "dias_entrega": random.randint(1, 7),
                "estado": "ACTIVO",
            }
        ]
    return cuerpo


def generar_payload_actualizacion_proveedor(etiqueta: str = "LT") -> dict[str, Any]:
    """Construye un cuerpo JSON valido para PUT /proveedores/{id}."""
    sufijo = uuid.uuid4().hex[:8]
    ciudad = random.choice(CIUDADES_COLOMBIA)
    return {
        "razon_social": f"Proveedor {etiqueta} Actualizado {sufijo.upper()} S.A.S.",
        "telefono": f"+57 601 {random.randint(2000000, 9999999)}",
        "email": f"actualizado.{sufijo}@lt-proveedores.example.co",
        "direccion": f"Carrera {random.randint(7, 110)} # {random.randint(1, 90)}-{random.randint(10, 99)}, {ciudad}",
    }


def generar_payload_contacto(etiqueta: str = "LT") -> dict[str, Any]:
    """Construye un cuerpo JSON valido para POST/PUT /proveedores/{id}/contactos."""
    sufijo = uuid.uuid4().hex[:8]
    return {
        "nombre": f"Contacto {etiqueta} {sufijo.upper()}",
        "cargo": random.choice(CARGOS_CONTACTO),
        "telefono": f"+57 31{random.randint(0, 9)} {random.randint(1000000, 9999999)}",
        "email": f"contacto.{sufijo}@lt-proveedores.example.co",
    }


def generar_payload_producto(estado: str = "ACTIVO") -> dict[str, Any]:
    """Construye un cuerpo JSON valido para PUT /proveedores/{id}/productos/{sku}."""
    return {
        "precio_compra": f"{random.uniform(850.0, 65000.0):.2f}",
        "dias_entrega": random.randint(1, 10),
        "estado": estado,
    }


def validar_json(response: Any, codigos_esperados: tuple[int, ...] = (200,)) -> Any | None:
    """Valida codigo HTTP esperado y cuerpo JSON parseable en catch_response=True."""
    if response.status_code not in codigos_esperados:
        response.failure(
            f"HTTP {response.status_code} (esperado {codigos_esperados}): {response.text[:160]}"
        )
        return None
    try:
        return response.json()
    except ValueError as exc:
        response.failure(f"Respuesta no es JSON valido: {exc}")
        return None


def validar_respuesta_paginada(response: Any) -> dict[str, Any] | None:
    """Valida la estructura {data: list, meta: {page, per_page, total}}."""
    datos = validar_json(response, (200,))
    if datos is None:
        return None
    if not isinstance(datos, dict) or not isinstance(datos.get("data"), list):
        response.failure("Falta arreglo 'data' en respuesta paginada")
        return None
    meta = datos.get("meta")
    if not isinstance(meta, dict) or not {"page", "per_page", "total"} <= set(meta.keys()):
        response.failure("Metadatos de paginacion 'meta' incompletos")
        return None
    response.success()
    return datos


def validar_proveedor(response: Any, codigo_esperado: int = 200) -> dict[str, Any] | None:
    """Valida estructura basica de un objeto proveedor."""
    datos = validar_json(response, (codigo_esperado,))
    if datos is None:
        return None
    claves = {"id_proveedor", "nit", "razon_social", "estado"}
    if not isinstance(datos, dict) or not claves <= set(datos.keys()):
        response.failure("Objeto proveedor incompleto en la respuesta JSON")
        return None
    response.success()
    return datos


def validar_contacto(response: Any, codigo_esperado: int = 201) -> dict[str, Any] | None:
    """Valida estructura basica de un objeto contacto."""
    datos = validar_json(response, (codigo_esperado,))
    if datos is None:
        return None
    claves = {"id_contacto", "nombre", "cargo", "email"}
    if not isinstance(datos, dict) or not claves <= set(datos.keys()):
        response.failure("Objeto contacto incompleto en la respuesta JSON")
        return None
    response.success()
    return datos


def validar_producto(response: Any, codigo_esperado: int = 200) -> dict[str, Any] | None:
    """Valida estructura basica de un objeto producto suministrado."""
    datos = validar_json(response, (codigo_esperado,))
    if datos is None:
        return None
    claves = {"sku", "precio_compra", "dias_entrega", "estado"}
    if not isinstance(datos, dict) or not claves <= set(datos.keys()):
        response.failure("Objeto producto suministrado incompleto en la respuesta JSON")
        return None
    response.success()
    return datos


def descubrir_contexto_inicial(environment: Any) -> None:
    """Consulta /health/ready y GET /proveedores al iniciar para descubrir IDs y SKUs reales."""
    if CONTEXTO_PROVEEDORES["inicializado"]:
        return

    host = (environment.host or HOST_DEFECTO).rstrip("/")
    cabeceras = construir_cabeceras(rol="admin", prefijo_correlacion="lt-prov-init")

    try:
        r_ready = requests.get(f"{host}/health/ready", timeout=5)
        if r_ready.status_code != 200:
            logger.warning(
                "MS-Proveedores /health/ready respondio HTTP %s en %s",
                r_ready.status_code,
                host,
            )
    except requests.RequestException as exc:
        logger.warning("No se pudo verificar /health/ready en %s: %s", host, exc)
        return

    try:
        r_prov = requests.get(
            f"{host}/proveedores",
            params={"page": 1, "per_page": 100},
            headers=cabeceras,
            timeout=10,
        )
        if r_prov.status_code == 200:
            cuerpo = r_prov.json()
            filas = cuerpo.get("data", [])
            ids_todos = [int(p["id_proveedor"]) for p in filas if "id_proveedor" in p]
            ids_activos = [
                int(p["id_proveedor"])
                for p in filas
                if p.get("estado") == "ACTIVO" and "id_proveedor" in p
            ]
            if ids_todos:
                CONTEXTO_PROVEEDORES["ids_todos"] = ids_todos
            if ids_activos:
                CONTEXTO_PROVEEDORES["ids_activos"] = ids_activos

            skus_encontrados: set[str] = set()
            for pid in CONTEXTO_PROVEEDORES["ids_activos"][:10]:
                r_prod = requests.get(
                    f"{host}/proveedores/{pid}/productos",
                    headers=cabeceras,
                    timeout=5,
                )
                if r_prod.status_code == 200 and isinstance(r_prod.json(), list):
                    for prod in r_prod.json():
                        if prod.get("estado") == "ACTIVO" and prod.get("sku"):
                            skus_encontrados.add(str(prod["sku"]))
            if skus_encontrados:
                CONTEXTO_PROVEEDORES["skus_activos"] = sorted(skus_encontrados)

            CONTEXTO_PROVEEDORES["inicializado"] = True
            logger.info(
                "Contexto inicial MS-Proveedores cargado: %d proveedores (%d activos), %d SKUs activos",
                len(CONTEXTO_PROVEEDORES["ids_todos"]),
                len(CONTEXTO_PROVEEDORES["ids_activos"]),
                len(CONTEXTO_PROVEEDORES["skus_activos"]),
            )
        else:
            logger.warning(
                "GET /proveedores en bootstrap devolvio HTTP %s. Verifica SERVICE_TOKEN.",
                r_prov.status_code,
            )
    except requests.RequestException as exc:
        logger.warning("Error consultando catalogo inicial en %s: %s", host, exc)


@events.test_start.add_listener
def _al_iniciar_prueba(environment: Any, **_kwargs: Any) -> None:
    descubrir_contexto_inicial(environment)


def crear_forma_estres(
    nombre_clase: str,
    paso_usuarios_defecto: int,
    paso_segundos_defecto: int,
    maximo_usuarios_defecto: int,
    limite_errores_defecto: float = 0.05,
    min_peticiones_quiebre: int = 20,
) -> type[LoadTestShape]:
    """Crea una clase LoadTestShape de estres escalonado con deteccion de quiebre.

    Registra en log el nivel de concurrencia, RPS y tasa de error en el momento
    en que se supera el umbral de fallos (diapositiva 6 de locust_test.pdf).
    """
    paso_usuarios = int(os.getenv("LT_PASO_USUARIOS", str(paso_usuarios_defecto)))
    paso_segundos = int(os.getenv("LT_PASO_SEGUNDOS", str(paso_segundos_defecto)))
    maximo_usuarios = int(os.getenv("LT_MAX_USUARIOS", str(maximo_usuarios_defecto)))
    limite_errores = float(os.getenv("LT_LIMITE_ERRORES", str(limite_errores_defecto)))

    class _FormaEstresBase(LoadTestShape):
        _quiebre_registrado = False

        def tick(self) -> tuple[int, float] | None:
            tiempo = self.get_run_time()
            total = self.runner.stats.total
            if (
                total.num_requests >= min_peticiones_quiebre
                and total.fail_ratio > limite_errores
            ):
                if not self._quiebre_registrado:
                    self._quiebre_registrado = True
                    logger.warning(
                        "[%s] Punto de quiebre detectado: usuarios=%d, tiempo=%.1fs, "
                        "rps=%.2f, tasa_error=%.2f%% (%d/%d)",
                        nombre_clase,
                        self.runner.user_count,
                        tiempo,
                        total.current_rps,
                        total.fail_ratio * 100.0,
                        total.num_failures,
                        total.num_requests,
                    )
                return None

            escalon = int(tiempo // paso_segundos) + 1
            usuarios = escalon * paso_usuarios
            if usuarios > maximo_usuarios:
                return None
            return usuarios, float(paso_usuarios)

    _FormaEstresBase.__name__ = nombre_clase
    return _FormaEstresBase
