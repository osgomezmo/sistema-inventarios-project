"""P11 - Prueba de Carga: Mezcla GET predominante (75%) + ciclo de ordenes (25%) (Integrado).

Tipo segun locust_test.pdf: Carga (diapositiva 16: mezcla de GET predominante y POST minoritario).
Dependencias: MS-Compras + MySQL + RabbitMQ (redapi) + MS-Proveedores (o mock_proveedores.py).
Parametros recomendados: -u 20 -r 4 -t 10m (ajustable por entorno o CLI).
SLO objetivo: p95 < 1200 ms y tasa de error < 1%.
"""

from __future__ import annotations

import random

from locust import HttpUser, events, tag, task

from common import (
    HOST_DEFECTO,
    construir_cabeceras,
    descubrir_ordenes_base,
    generar_payload_orden,
    pausa_configurada,
    validar_listado_paginado,
    validar_orden_objeto,
    verificar_readiness_integrado,
)

CONTEXTO: dict[str, object] = {"ids": [1, 2, 3, 4, 5]}


@events.test_start.add_listener
def al_iniciar(environment, **_kwargs) -> None:
    host = environment.host or HOST_DEFECTO
    info = descubrir_ordenes_base(host)
    verificar_readiness_integrado(host)
    CONTEXTO["ids"] = info["ids"]


class UsuarioOperacionMixtaCompras(HttpUser):
    """Simula trafico operativo nominal 75% lectura y 25% escritura en MS-Compras."""

    host = HOST_DEFECTO
    wait_time = pausa_configurada(1.0, 3.0)

    @tag("p11", "carga", "integrado")
    @task(4)
    def leer_listado_ordenes(self) -> None:
        with self.client.get(
            "/ordenes-compra",
            params={"page": 1, "per_page": 20},
            headers=construir_cabeceras(rol="compras"),
            name="P11 GET /ordenes-compra",
            catch_response=True,
        ) as resp:
            validar_listado_paginado(resp)

    @tag("p11", "carga", "integrado")
    @task(3)
    def leer_detalle_orden(self) -> None:
        ids: list[int] = CONTEXTO["ids"]  # type: ignore[assignment]
        id_orden = random.choice(ids)
        with self.client.get(
            f"/ordenes-compra/{id_orden}",
            headers=construir_cabeceras(rol="gerente"),
            name="P11 GET /ordenes-compra/{id}",
            catch_response=True,
        ) as resp:
            validar_orden_objeto(resp, status_esperado=200)

    @tag("p11", "carga", "integrado")
    @task(2)
    def leer_devoluciones(self) -> None:
        with self.client.get(
            "/devoluciones-proveedor",
            params={"page": 1, "per_page": 20},
            headers=construir_cabeceras(rol="jefe_bodega"),
            name="P11 GET /devoluciones-proveedor",
            catch_response=True,
        ) as resp:
            validar_listado_paginado(resp)

    @tag("p11", "carga", "integrado")
    @task(3)
    def ciclo_borrador_editar_decidir(self) -> None:
        """Crea orden BORRADOR, la actualiza y la aprueba o anula sin colisiones entre VUs."""
        payload_inicial = generar_payload_orden(num_items=2, cantidad="15.000")
        id_orden: int | None = None

        with self.client.post(
            "/ordenes-compra",
            json=payload_inicial,
            headers=construir_cabeceras(rol="compras"),
            name="P11 POST /ordenes-compra",
            catch_response=True,
        ) as resp:
            creada = validar_orden_objeto(resp, status_esperado=201, estado_esperado="BORRADOR")
            if creada is not None:
                id_orden = int(creada["id_orden"])

        if id_orden is None:
            return

        payload_actualizado = generar_payload_orden(num_items=2, cantidad="20.000")
        with self.client.put(
            f"/ordenes-compra/{id_orden}",
            json=payload_actualizado,
            headers=construir_cabeceras(rol="compras"),
            name="P11 PUT /ordenes-compra/{id}",
            catch_response=True,
        ) as resp:
            actualizada = validar_orden_objeto(resp, status_esperado=200, estado_esperado="BORRADOR")
            if actualizada is None:
                return

        if random.random() < 0.7:
            with self.client.post(
                f"/ordenes-compra/{id_orden}/aprobar",
                headers=construir_cabeceras(rol="gerente"),
                name="P11 POST /ordenes-compra/{id}/aprobar",
                catch_response=True,
            ) as resp:
                validar_orden_objeto(resp, status_esperado=200, estado_esperado="APROBADA")
        else:
            with self.client.post(
                f"/ordenes-compra/{id_orden}/anular",
                json={"motivo": "Anulacion controlada en prueba P11"},
                headers=construir_cabeceras(rol="gerente"),
                name="P11 POST /ordenes-compra/{id}/anular",
                catch_response=True,
            ) as resp:
                validar_orden_objeto(resp, status_esperado=200, estado_esperado="ANULADA")
