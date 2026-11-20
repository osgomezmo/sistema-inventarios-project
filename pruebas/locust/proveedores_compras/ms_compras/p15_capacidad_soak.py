"""P15 - Prueba de Capacidad (Soak): Carga alta sostenida prolongada (Modo Solo u Opcional Mixto).

Tipo segun locust_test.pdf: Capacidad (soak) (diapositivas 7 y 16: carga alta
cercana al maximo estable —no al quiebre— durante un periodo prolongado de 60 min
o mas, para detectar degradacion gradual de memoria, pool de conexiones MySQL e I/O).
Dependencias:
  - Por defecto (LT_INCLUIR_ESCRITURAS=0): 100% SOLO (solo MS-Compras + su MySQL).
  - Con LT_INCLUIR_ESCRITURAS=1: INTEGRADO (requiere MS-Proveedores + RabbitMQ).
Parametros recomendados: -u 40 -r 5 -t 60m (reducible con LT_DURACION=5m para validacion).
SLO / Criterio de tendencia: p95 < 1000 ms, tasa de error < 0.5% y deriva de p95
entre el primer y ultimo cuarto del archivo *_stats_history.csv menor al 20%.
"""

from __future__ import annotations

import os
import random

from locust import HttpUser, events, tag, task

from common import (
    ESTADOS_VALIDOS,
    HOST_DEFECTO,
    PROVEEDOR_IDS,
    construir_cabeceras,
    descubrir_ordenes_base,
    generar_payload_orden,
    pausa_configurada,
    rango_fechas_reciente,
    validar_listado_paginado,
    validar_orden_objeto,
    verificar_readiness_integrado,
)

INCLUIR_ESCRITURAS = os.getenv("LT_INCLUIR_ESCRITURAS", "0").strip().lower() in {
    "1",
    "true",
    "si",
    "yes",
}
CONTEXTO: dict[str, object] = {"ids": [1, 2, 3, 4, 5]}


@events.test_start.add_listener
def al_iniciar(environment, **_kwargs) -> None:
    host = environment.host or HOST_DEFECTO
    info = descubrir_ordenes_base(host)
    if INCLUIR_ESCRITURAS:
        verificar_readiness_integrado(host)
    CONTEXTO["ids"] = info["ids"]


class UsuarioCapacidadSoakCompras(HttpUser):
    """Mantiene carga estable prolongada para analizar tendencia temporal y recursos."""

    host = HOST_DEFECTO
    wait_time = pausa_configurada(1.0, 2.0)

    @tag("p15", "capacidad", "soak", "solo")
    @task(5)
    def listar_ordenes_con_filtros(self) -> None:
        desde, hasta = rango_fechas_reciente(dias=45)
        params: dict[str, object] = {
            "page": 1,
            "per_page": random.choice((10, 20, 50)),
            "desde": desde,
            "hasta": hasta,
        }
        if random.random() < 0.5:
            params["estado"] = random.choice(ESTADOS_VALIDOS)
        with self.client.get(
            "/ordenes-compra",
            params=params,
            headers=construir_cabeceras(rol="compras"),
            name="P15 GET /ordenes-compra",
            catch_response=True,
        ) as resp:
            validar_listado_paginado(resp)

    @tag("p15", "capacidad", "soak", "solo")
    @task(4)
    def detalle_orden(self) -> None:
        ids: list[int] = CONTEXTO["ids"]  # type: ignore[assignment]
        id_orden = random.choice(ids)
        with self.client.get(
            f"/ordenes-compra/{id_orden}",
            headers=construir_cabeceras(rol="admin"),
            name="P15 GET /ordenes-compra/{id}",
            catch_response=True,
        ) as resp:
            validar_orden_objeto(resp, status_esperado=200)

    @tag("p15", "capacidad", "soak", "solo")
    @task(2)
    def listar_recepciones_orden(self) -> None:
        ids: list[int] = CONTEXTO["ids"]  # type: ignore[assignment]
        id_orden = random.choice(ids)
        with self.client.get(
            f"/ordenes-compra/{id_orden}/recepciones",
            headers=construir_cabeceras(rol="jefe_bodega"),
            name="P15 GET /ordenes-compra/{id}/recepciones",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")
                return
            try:
                datos = resp.json()
            except ValueError:
                resp.failure("JSON invalido")
                return
            if isinstance(datos, list):
                resp.success()
            else:
                resp.failure("Respuesta no es lista")

    @tag("p15", "capacidad", "soak", "solo")
    @task(2)
    def listar_devoluciones(self) -> None:
        with self.client.get(
            "/devoluciones-proveedor",
            params={
                "page": 1,
                "per_page": 20,
                "id_proveedor": random.choice(PROVEEDOR_IDS),
            },
            headers=construir_cabeceras(rol="compras"),
            name="P15 GET /devoluciones-proveedor",
            catch_response=True,
        ) as resp:
            validar_listado_paginado(resp)

    @tag("p15", "capacidad", "soak", "solo")
    @task(1)
    def verificar_salud_continua(self) -> None:
        ruta = "/health/ready" if INCLUIR_ESCRITURAS else "/health"
        with self.client.get(
            ruta,
            name=f"P15 GET {ruta}",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")
                return
            try:
                cuerpo = resp.json()
            except ValueError:
                resp.failure("JSON invalido en health")
                return
            if cuerpo.get("status") == "ok":
                resp.success()
            else:
                resp.failure(f"Estado inesperado: {cuerpo}")

    @tag("p15", "capacidad", "soak", "integrado")
    @task(1)
    def escritura_opcional_soak(self) -> None:
        """Ejecuta una escritura ligera solo cuando LT_INCLUIR_ESCRITURAS=1."""
        if not INCLUIR_ESCRITURAS:
            return
        payload = generar_payload_orden(num_items=1, cantidad="2.000")
        id_orden: int | None = None
        with self.client.post(
            "/ordenes-compra",
            json=payload,
            headers=construir_cabeceras(rol="compras"),
            name="P15 POST /ordenes-compra (soak mixto)",
            catch_response=True,
        ) as resp:
            creada = validar_orden_objeto(resp, status_esperado=201, estado_esperado="BORRADOR")
            if creada is not None:
                id_orden = int(creada["id_orden"])
        if id_orden is not None:
            with self.client.post(
                f"/ordenes-compra/{id_orden}/anular",
                json={"motivo": "Cierre controlado en prueba soak P15"},
                headers=construir_cabeceras(rol="gerente"),
                name="P15 POST /ordenes-compra/{id}/anular (soak mixto)",
                catch_response=True,
            ) as resp:
                validar_orden_objeto(resp, status_esperado=200, estado_esperado="ANULADA")
