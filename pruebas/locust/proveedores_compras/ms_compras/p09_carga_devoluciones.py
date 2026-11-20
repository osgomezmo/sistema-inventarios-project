"""P09 - Prueba de Carga: Devoluciones, filtros temporales y paginacion (Modo Solo).

Tipo segun locust_test.pdf: Carga (comportamiento nominal y analisis de paginacion e indices).
Dependencias: Solo MS-Compras + su MySQL (sin RabbitMQ ni MS-Proveedores).
Parametros recomendados: -u 25 -r 5 -t 10m (ajustable por entorno o CLI).
SLO objetivo: p95 < 600 ms y tasa de error < 1%.
"""

from __future__ import annotations

import random

from locust import HttpUser, events, tag, task

from common import (
    HOST_DEFECTO,
    PROVEEDOR_IDS,
    construir_cabeceras,
    descubrir_ordenes_base,
    pausa_configurada,
    rango_fechas_reciente,
    validar_listado_paginado,
)

CONTEXTO: dict[str, object] = {"ids": [1, 2, 3, 4, 5]}


@events.test_start.add_listener
def al_iniciar(environment, **_kwargs) -> None:
    host = environment.host or HOST_DEFECTO
    info = descubrir_ordenes_base(host)
    CONTEXTO["ids"] = info["ids"]


class UsuarioDevolucionesYPaginacion(HttpUser):
    """Ejercita consultas de devoluciones con JOINs y rangos de fecha/paginacion."""

    host = HOST_DEFECTO
    wait_time = pausa_configurada(1.0, 2.5)

    def _rol_devoluciones(self) -> str:
        # GET /devoluciones-proveedor permite admin, jefe_bodega y compras (no gerente).
        return random.choice(("admin", "jefe_bodega", "compras"))

    @tag("p09", "carga", "solo")
    @task(4)
    def listar_devoluciones_paginadas(self) -> None:
        per_page = random.choice((10, 20, 50, 100))
        with self.client.get(
            "/devoluciones-proveedor",
            params={"page": 1, "per_page": per_page},
            headers=construir_cabeceras(rol=self._rol_devoluciones()),
            name="P09 GET /devoluciones-proveedor (paginado)",
            catch_response=True,
        ) as resp:
            validar_listado_paginado(resp)

    @tag("p09", "carga", "solo")
    @task(3)
    def listar_devoluciones_por_proveedor_y_fechas(self) -> None:
        desde, hasta = rango_fechas_reciente(dias=random.choice((7, 30, 90)))
        params = {
            "page": 1,
            "per_page": 20,
            "id_proveedor": random.choice(PROVEEDOR_IDS),
            "desde": desde,
            "hasta": hasta,
        }
        with self.client.get(
            "/devoluciones-proveedor",
            params=params,
            headers=construir_cabeceras(rol=self._rol_devoluciones()),
            name="P09 GET /devoluciones-proveedor (filtro proveedor+fechas)",
            catch_response=True,
        ) as resp:
            validar_listado_paginado(resp)

    @tag("p09", "carga", "solo")
    @task(3)
    def comparar_ordenes_pagina_pequena_vs_maxima(self) -> None:
        desde, hasta = rango_fechas_reciente(dias=60)
        per_page = random.choice((10, 100))
        nombre = (
            "P09 GET /ordenes-compra (per_page=100+fechas)"
            if per_page == 100
            else "P09 GET /ordenes-compra (per_page=10+fechas)"
        )
        with self.client.get(
            "/ordenes-compra",
            params={"page": 1, "per_page": per_page, "desde": desde, "hasta": hasta},
            headers=construir_cabeceras(rol="compras"),
            name=nombre,
            catch_response=True,
        ) as resp:
            validar_listado_paginado(resp)

    @tag("p09", "carga", "solo")
    @task(2)
    def consultar_recepciones_de_ordenes_con_movimiento(self) -> None:
        ids: list[int] = CONTEXTO["ids"]  # type: ignore[assignment]
        id_orden = random.choice(ids)
        with self.client.get(
            f"/ordenes-compra/{id_orden}/recepciones",
            headers=construir_cabeceras(rol="jefe_bodega"),
            name="P09 GET /ordenes-compra/{id}/recepciones",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")
                return
            try:
                datos = resp.json()
            except ValueError:
                resp.failure("Respuesta no es JSON valido")
                return
            if isinstance(datos, list):
                resp.success()
            else:
                resp.failure("Se esperaba una lista de recepciones")
