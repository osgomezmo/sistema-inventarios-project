"""P12 - Prueba de Carga: Ciclo transaccional completo con recepciones y devoluciones (Integrado).

Tipo segun locust_test.pdf: Carga (flujo transaccional de negocio completo con
bloqueos pesimistas FOR UPDATE y publicacion de 3 eventos en RabbitMQ:
OrdenCompraActualizada, MercanciaRecibida y DevolucionProveedorRegistrada).
Dependencias: MS-Compras + MySQL + RabbitMQ (redapi) + MS-Proveedores (o mock_proveedores.py).
Parametros recomendados: -u 15 -r 3 -t 10m (ajustable por entorno o CLI).
SLO objetivo: p95 < 1500 ms y tasa de error < 1%.
"""

from __future__ import annotations

from typing import Any

from locust import HttpUser, SequentialTaskSet, events, tag, task

from common import (
    HOST_DEFECTO,
    construir_cabeceras,
    descubrir_ordenes_base,
    generar_payload_orden,
    pausa_configurada,
    validar_orden_objeto,
    verificar_readiness_integrado,
)


@events.test_start.add_listener
def al_iniciar(environment, **_kwargs) -> None:
    host = environment.host or HOST_DEFECTO
    descubrir_ordenes_base(host)
    verificar_readiness_integrado(host)


class FlujoCompletoCompraRecepcionDevolucion(SequentialTaskSet):
    """Ejecuta el ciclo de vida completo sobre una orden aislada por usuario virtual."""

    id_orden: int | None = None
    detalles: list[dict[str, Any]] = []

    @tag("p12", "carga", "integrado")
    @task
    def paso_1_crear_orden(self) -> None:
        self.id_orden = None
        self.detalles = []
        payload = generar_payload_orden(num_items=2, cantidad="10.000")
        with self.client.post(
            "/ordenes-compra",
            json=payload,
            headers=construir_cabeceras(rol="compras"),
            name="P12-1 POST /ordenes-compra",
            catch_response=True,
        ) as resp:
            orden = validar_orden_objeto(resp, status_esperado=201, estado_esperado="BORRADOR")
            if orden is not None:
                self.id_orden = int(orden["id_orden"])
                self.detalles = list(orden.get("items", []))

    @tag("p12", "carga", "integrado")
    @task
    def paso_2_aprobar_orden(self) -> None:
        if self.id_orden is None:
            return
        with self.client.post(
            f"/ordenes-compra/{self.id_orden}/aprobar",
            headers=construir_cabeceras(rol="gerente"),
            name="P12-2 POST /ordenes-compra/{id}/aprobar",
            catch_response=True,
        ) as resp:
            aprobada = validar_orden_objeto(resp, status_esperado=200, estado_esperado="APROBADA")
            if aprobada is None:
                self.id_orden = None

    @tag("p12", "carga", "integrado")
    @task
    def paso_3_recepcion_parcial(self) -> None:
        if self.id_orden is None or not self.detalles:
            return
        items_parciales = [
            {"id_detalle": int(det["id_detalle"]), "cantidad": "4.000"}
            for det in self.detalles
        ]
        with self.client.post(
            f"/ordenes-compra/{self.id_orden}/recepciones",
            json={
                "observaciones": "Entrega parcial 40% - prueba P12",
                "items": items_parciales,
            },
            headers=construir_cabeceras(rol="jefe_bodega"),
            name="P12-3 POST /ordenes-compra/{id}/recepciones (parcial)",
            catch_response=True,
        ) as resp:
            if resp.status_code != 201:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:160]}")
                self.id_orden = None
                return
            cuerpo = resp.json()
            if cuerpo.get("estado_orden") != "RECIBIDA_PARCIAL":
                resp.failure(f"Se esperaba RECIBIDA_PARCIAL, llego {cuerpo.get('estado_orden')}")
                self.id_orden = None
            else:
                resp.success()

    @tag("p12", "carga", "integrado")
    @task
    def paso_4_recepcion_final(self) -> None:
        if self.id_orden is None or not self.detalles:
            return
        items_restantes = [
            {"id_detalle": int(det["id_detalle"]), "cantidad": "6.000"}
            for det in self.detalles
        ]
        with self.client.post(
            f"/ordenes-compra/{self.id_orden}/recepciones",
            json={
                "observaciones": "Entrega final 60% - prueba P12",
                "items": items_restantes,
            },
            headers=construir_cabeceras(rol="jefe_bodega"),
            name="P12-4 POST /ordenes-compra/{id}/recepciones (total)",
            catch_response=True,
        ) as resp:
            if resp.status_code != 201:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:160]}")
                self.id_orden = None
                return
            cuerpo = resp.json()
            if cuerpo.get("estado_orden") != "RECIBIDA":
                resp.failure(f"Se esperaba RECIBIDA, llego {cuerpo.get('estado_orden')}")
                self.id_orden = None
            else:
                resp.success()

    @tag("p12", "carga", "integrado")
    @task
    def paso_5_devolucion_parcial(self) -> None:
        if self.id_orden is None or not self.detalles:
            return
        primer_detalle = int(self.detalles[0]["id_detalle"])
        with self.client.post(
            f"/ordenes-compra/{self.id_orden}/devoluciones",
            json={
                "motivo": "Empaque averiado detectado en control de calidad P12",
                "items": [{"id_detalle": primer_detalle, "cantidad": "1.000"}],
            },
            headers=construir_cabeceras(rol="jefe_bodega"),
            name="P12-5 POST /ordenes-compra/{id}/devoluciones",
            catch_response=True,
        ) as resp:
            if resp.status_code != 201:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:160]}")
                return
            cuerpo = resp.json()
            if "id_devolucion" not in cuerpo:
                resp.failure("Respuesta sin id_devolucion")
            else:
                resp.success()

    @tag("p12", "carga", "integrado")
    @task
    def paso_6_verificar_orden_completa(self) -> None:
        if self.id_orden is None:
            return
        with self.client.get(
            f"/ordenes-compra/{self.id_orden}",
            headers=construir_cabeceras(rol="admin"),
            name="P12-6 GET /ordenes-compra/{id} (consistencia)",
            catch_response=True,
        ) as resp:
            orden = validar_orden_objeto(resp, status_esperado=200, estado_esperado="RECIBIDA")
            if orden is not None:
                if len(orden.get("recepciones", [])) < 2 or len(orden.get("devoluciones", [])) < 1:
                    resp.failure("Consistencia incompleta en recepciones/devoluciones")


class UsuarioCicloRecepcionesDevoluciones(HttpUser):
    """Usuario virtual que ejecuta la secuencia transaccional completa de MS-Compras."""

    host = HOST_DEFECTO
    wait_time = pausa_configurada(1.0, 2.5)
    tasks = [FlujoCompletoCompraRecepcionDevolucion]
