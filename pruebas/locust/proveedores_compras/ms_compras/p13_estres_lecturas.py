"""P13 - Prueba de Estres: Saturacion progresiva de lecturas y pool MySQL/Gunicorn (Solo).

Tipo segun locust_test.pdf: Estres (diapositivas 6 y 16: incremento progresivo
de carga mas alla del diseno nominal hasta detectar punto de degradacion/quiebre
y registrar concurrencia/RPS asociados).
Dependencias: Solo MS-Compras + su MySQL (sin RabbitMQ ni MS-Proveedores).
Perfil por defecto (LoadTestShape): 20 -> 200 usuarios (+20 cada 30 s), pausa
0.3-1.0 s, corte automatico si tasa de error supera 5%.
Variables ajustables: LT_PASO_USUARIOS, LT_PASO_SEGUNDOS, LT_MAX_USUARIOS, LT_LIMITE_ERRORES.
"""

from __future__ import annotations

import os
import random

from locust import HttpUser, events, tag, task

from common import (
    ESTADOS_VALIDOS,
    FormaEstresEscalonada,
    HOST_DEFECTO,
    PROVEEDOR_IDS,
    construir_cabeceras,
    descubrir_ordenes_base,
    pausa_configurada,
    rango_fechas_reciente,
    validar_listado_paginado,
    validar_orden_objeto,
)

CONTEXTO: dict[str, object] = {"ids": [1, 2, 3, 4, 5]}


@events.test_start.add_listener
def al_iniciar(environment, **_kwargs) -> None:
    host = environment.host or HOST_DEFECTO
    info = descubrir_ordenes_base(host)
    CONTEXTO["ids"] = info["ids"]


class FormaEstresLecturas(FormaEstresEscalonada):
    """Escalones progresivos para encontrar el limite de Gunicorn (2x4) y pool MySQL."""

    paso_usuarios = int(os.getenv("LT_PASO_USUARIOS", "20"))
    paso_segundos = int(os.getenv("LT_PASO_SEGUNDOS", "30"))
    max_usuarios = int(os.getenv("LT_MAX_USUARIOS", "200"))
    limite_errores = float(os.getenv("LT_LIMITE_ERRORES", "0.05"))


class UsuarioEstresLecturasCompras(HttpUser):
    """Genera lecturas intensivas con JOINs para presionar pool de conexiones y CPU."""

    host = HOST_DEFECTO
    wait_time = pausa_configurada(0.3, 1.0)

    @tag("p13", "estres", "solo")
    @task(4)
    def listar_ordenes_lote_grande(self) -> None:
        desde, hasta = rango_fechas_reciente(dias=90)
        params: dict[str, object] = {
            "page": 1,
            "per_page": 50,
            "desde": desde,
            "hasta": hasta,
        }
        if random.random() < 0.4:
            params["estado"] = random.choice(ESTADOS_VALIDOS)
        with self.client.get(
            "/ordenes-compra",
            params=params,
            headers=construir_cabeceras(rol="admin"),
            name="P13 GET /ordenes-compra (per_page=50)",
            catch_response=True,
        ) as resp:
            validar_listado_paginado(resp)

    @tag("p13", "estres", "solo")
    @task(4)
    def detalle_completo_con_joins(self) -> None:
        ids: list[int] = CONTEXTO["ids"]  # type: ignore[assignment]
        id_orden = random.choice(ids)
        with self.client.get(
            f"/ordenes-compra/{id_orden}",
            headers=construir_cabeceras(rol="compras"),
            name="P13 GET /ordenes-compra/{id}",
            catch_response=True,
        ) as resp:
            validar_orden_objeto(resp, status_esperado=200)

    @tag("p13", "estres", "solo")
    @task(2)
    def listar_recepciones_orden(self) -> None:
        ids: list[int] = CONTEXTO["ids"]  # type: ignore[assignment]
        id_orden = random.choice(ids)
        with self.client.get(
            f"/ordenes-compra/{id_orden}/recepciones",
            headers=construir_cabeceras(rol="jefe_bodega"),
            name="P13 GET /ordenes-compra/{id}/recepciones",
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

    @tag("p13", "estres", "solo")
    @task(2)
    def listar_devoluciones_con_join(self) -> None:
        with self.client.get(
            "/devoluciones-proveedor",
            params={
                "page": 1,
                "per_page": 50,
                "id_proveedor": random.choice(PROVEEDOR_IDS),
            },
            headers=construir_cabeceras(rol="compras"),
            name="P13 GET /devoluciones-proveedor (JOIN)",
            catch_response=True,
        ) as resp:
            validar_listado_paginado(resp)
