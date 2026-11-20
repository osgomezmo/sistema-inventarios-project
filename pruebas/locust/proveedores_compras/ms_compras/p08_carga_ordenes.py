"""P08 - Prueba de Carga: Consultas mixtas de ordenes de compra (Modo Solo).

Tipo segun locust_test.pdf: Carga (comportamiento nominal sostenido en meseta).
Dependencias: Solo MS-Compras + su MySQL (sin RabbitMQ ni MS-Proveedores).
Parametros recomendados: -u 20 -r 5 -t 10m (ajustable por entorno o CLI).
SLO objetivo: p95 < 500 ms y tasa de error < 1%.
"""

from __future__ import annotations

import random

from locust import HttpUser, events, tag, task

from common import (
    ESTADOS_VALIDOS,
    HOST_DEFECTO,
    PROVEEDOR_IDS,
    construir_cabeceras,
    descubrir_ordenes_base,
    pausa_configurada,
    validar_listado_paginado,
    validar_orden_objeto,
)

CONTEXTO: dict[str, object] = {"ids": [1, 2, 3, 4, 5]}


@events.test_start.add_listener
def al_iniciar(environment, **_kwargs) -> None:
    host = environment.host or HOST_DEFECTO
    info = descubrir_ordenes_base(host)
    CONTEXTO["ids"] = info["ids"]


class UsuarioConsultasOrdenes(HttpUser):
    """Simula usuarios de compras/bodega/gerencia consultando ordenes de compra."""

    host = HOST_DEFECTO
    wait_time = pausa_configurada(1.0, 3.0)

    def _rol_lectura(self) -> str:
        return random.choice(("admin", "compras", "jefe_bodega", "gerente"))

    @tag("p08", "carga", "solo")
    @task(4)
    def listar_ordenes_paginadas(self) -> None:
        per_page = random.choice((10, 20, 50))
        with self.client.get(
            "/ordenes-compra",
            params={"page": 1, "per_page": per_page},
            headers=construir_cabeceras(rol=self._rol_lectura()),
            name="P08 GET /ordenes-compra (paginado)",
            catch_response=True,
        ) as resp:
            validar_listado_paginado(resp)

    @tag("p08", "carga", "solo")
    @task(3)
    def filtrar_ordenes_estado_proveedor(self) -> None:
        params: dict[str, object] = {
            "page": 1,
            "per_page": 20,
            "estado": random.choice(ESTADOS_VALIDOS),
        }
        if random.random() < 0.5:
            params["id_proveedor"] = random.choice(PROVEEDOR_IDS)

        with self.client.get(
            "/ordenes-compra",
            params=params,
            headers=construir_cabeceras(rol=self._rol_lectura()),
            name="P08 GET /ordenes-compra (filtros)",
            catch_response=True,
        ) as resp:
            validar_listado_paginado(resp)

    @tag("p08", "carga", "solo")
    @task(3)
    def obtener_detalle_orden(self) -> None:
        ids: list[int] = CONTEXTO["ids"]  # type: ignore[assignment]
        id_orden = random.choice(ids)
        with self.client.get(
            f"/ordenes-compra/{id_orden}",
            headers=construir_cabeceras(rol=self._rol_lectura()),
            name="P08 GET /ordenes-compra/{id}",
            catch_response=True,
        ) as resp:
            orden = validar_orden_objeto(resp, status_esperado=200)
            if orden is not None and not isinstance(orden.get("items"), list):
                resp.failure("Orden sin arreglo 'items'")

    @tag("p08", "carga", "solo")
    @task(2)
    def listar_recepciones_de_orden(self) -> None:
        ids: list[int] = CONTEXTO["ids"]  # type: ignore[assignment]
        id_orden = random.choice(ids)
        with self.client.get(
            f"/ordenes-compra/{id_orden}/recepciones",
            headers=construir_cabeceras(rol=self._rol_lectura()),
            name="P08 GET /ordenes-compra/{id}/recepciones",
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
            if not isinstance(datos, list):
                resp.failure("Se esperaba lista de recepciones")
            else:
                resp.success()

    @tag("p08", "carga", "solo")
    @task(1)
    def consultar_liveness(self) -> None:
        with self.client.get(
            "/health",
            name="P08 GET /health",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Liveness inesperado: HTTP {resp.status_code}")
                return
            try:
                cuerpo = resp.json()
            except ValueError:
                resp.failure("Liveness no retorno JSON valido")
                return
            if cuerpo.get("status") == "ok":
                resp.success()
            else:
                resp.failure(f"Estado inesperado en /health: {cuerpo}")
