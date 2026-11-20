"""P14 - Prueba de Estres: Rampa en flujo mixto con escrituras, FOR UPDATE y dependencias (Integrado).

Tipo segun locust_test.pdf: Estres (diapositivas 6 y 16: misma mezcla operativa
bajo rampa agresiva de usuarios hasta observar degradacion de latencia, timeouts
o errores 503 en MySQL, MS-Proveedores o RabbitMQ).
Dependencias: MS-Compras + MySQL + RabbitMQ (redapi) + MS-Proveedores (o mock_proveedores.py).
Perfil por defecto (LoadTestShape): 15 -> 120 usuarios (+15 cada 30 s), pausa
0.4-1.2 s, corte automatico si tasa de error supera 5%.
Variables ajustables: LT_PASO_USUARIOS, LT_PASO_SEGUNDOS, LT_MAX_USUARIOS, LT_LIMITE_ERRORES.
"""

from __future__ import annotations

import os
import random

from locust import HttpUser, events, tag, task

from common import (
    FormaEstresEscalonada,
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


class FormaEstresEscrituras(FormaEstresEscalonada):
    """Rampa agresiva para hallar el punto de quiebre transaccional y de RabbitMQ."""

    paso_usuarios = int(os.getenv("LT_PASO_USUARIOS", "15"))
    paso_segundos = int(os.getenv("LT_PASO_SEGUNDOS", "30"))
    max_usuarios = int(os.getenv("LT_MAX_USUARIOS", "120"))
    limite_errores = float(os.getenv("LT_LIMITE_ERRORES", "0.05"))


class UsuarioEstresMixtoCompras(HttpUser):
    """Combina lecturas y escrituras concurrentes sometiendo a estres todo el camino critico."""

    host = HOST_DEFECTO
    wait_time = pausa_configurada(0.4, 1.2)

    @tag("p14", "estres", "integrado")
    @task(4)
    def consulta_ordenes(self) -> None:
        with self.client.get(
            "/ordenes-compra",
            params={"page": 1, "per_page": 20},
            headers=construir_cabeceras(rol="compras"),
            name="P14 GET /ordenes-compra",
            catch_response=True,
        ) as resp:
            validar_listado_paginado(resp)

    @tag("p14", "estres", "integrado")
    @task(2)
    def consulta_detalle(self) -> None:
        ids: list[int] = CONTEXTO["ids"]  # type: ignore[assignment]
        id_orden = random.choice(ids)
        with self.client.get(
            f"/ordenes-compra/{id_orden}",
            headers=construir_cabeceras(rol="gerente"),
            name="P14 GET /ordenes-compra/{id}",
            catch_response=True,
        ) as resp:
            validar_orden_objeto(resp, status_esperado=200)

    @tag("p14", "estres", "integrado")
    @task(4)
    def escritura_crear_aprobar_recibir(self) -> None:
        """Crea orden, aprueba y recibe en una orden dedicada por ejecucion."""
        payload = generar_payload_orden(num_items=2, cantidad="5.000")
        id_orden: int | None = None
        detalles: list[dict[str, object]] = []

        with self.client.post(
            "/ordenes-compra",
            json=payload,
            headers=construir_cabeceras(rol="compras"),
            name="P14 POST /ordenes-compra",
            catch_response=True,
        ) as resp:
            creada = validar_orden_objeto(resp, status_esperado=201, estado_esperado="BORRADOR")
            if creada is not None:
                id_orden = int(creada["id_orden"])
                detalles = list(creada.get("items", []))

        if id_orden is None:
            return

        with self.client.post(
            f"/ordenes-compra/{id_orden}/aprobar",
            headers=construir_cabeceras(rol="gerente"),
            name="P14 POST /ordenes-compra/{id}/aprobar",
            catch_response=True,
        ) as resp:
            aprobada = validar_orden_objeto(resp, status_esperado=200, estado_esperado="APROBADA")
            if aprobada is None:
                return

        if not detalles:
            return

        items_rec = [
            {"id_detalle": int(det["id_detalle"]), "cantidad": "5.000"}
            for det in detalles
        ]
        with self.client.post(
            f"/ordenes-compra/{id_orden}/recepciones",
            json={"observaciones": "Recepcion bajo estres P14", "items": items_rec},
            headers=construir_cabeceras(rol="jefe_bodega"),
            name="P14 POST /ordenes-compra/{id}/recepciones",
            catch_response=True,
        ) as resp:
            if resp.status_code != 201:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:160]}")
                return
            try:
                cuerpo = resp.json()
            except ValueError:
                resp.failure("JSON invalido en recepcion")
                return
            if cuerpo.get("estado_orden") != "RECIBIDA":
                resp.failure(f"Estado inesperado {cuerpo.get('estado_orden')}")
            else:
                resp.success()
