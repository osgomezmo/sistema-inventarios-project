"""P10 - Prueba de Carga: Validacion, RBAC y conflictos de estado (Modo Solo).

Tipo segun locust_test.pdf: Carga (comportamiento nominal de rutas negativas y seguridad).
Dependencias: Solo MS-Compras + su MySQL. Todas las rutas ejercitadas fallan de
forma controlada ANTES de invocar a MS-Proveedores o RabbitMQ (401, 403, 404, 422, 409).
Parametros recomendados: -u 30 -r 6 -t 5m (ajustable por entorno o CLI).
SLO objetivo: p95 < 300 ms y 0% de desviaciones respecto al codigo HTTP esperado.
"""

from __future__ import annotations

import random

from locust import HttpUser, events, tag, task

from common import (
    HOST_DEFECTO,
    construir_cabeceras,
    descubrir_ordenes_base,
    pausa_configurada,
    validar_error_esperado,
)

CONTEXTO: dict[str, int] = {
    "id_recibida": 1,
    "id_borrador": 4,
    "id_anulada": 5,
}


@events.test_start.add_listener
def al_iniciar(environment, **_kwargs) -> None:
    host = environment.host or HOST_DEFECTO
    info = descubrir_ordenes_base(host)
    por_estado: dict[str, list[int]] = info["por_estado"]
    if por_estado.get("RECIBIDA"):
        CONTEXTO["id_recibida"] = por_estado["RECIBIDA"][0]
    if por_estado.get("BORRADOR"):
        CONTEXTO["id_borrador"] = por_estado["BORRADOR"][0]
    if por_estado.get("ANULADA"):
        CONTEXTO["id_anulada"] = por_estado["ANULADA"][0]


class UsuarioValidacionYSeguridad(HttpUser):
    """Mide latencia y consistencia de hooks de seguridad, validadores y maquina de estados."""

    host = HOST_DEFECTO
    wait_time = pausa_configurada(0.5, 1.5)

    @tag("p10", "carga", "solo")
    @task(2)
    def rechazo_sin_token_401(self) -> None:
        with self.client.get(
            "/ordenes-compra",
            headers=construir_cabeceras(incluir_auth=False),
            name="P10 GET /ordenes-compra (401 sin token)",
            catch_response=True,
        ) as resp:
            validar_error_esperado(resp, 401, "NO_AUTENTICADO")

    @tag("p10", "carga", "solo")
    @task(2)
    def rechazo_token_invalido_401(self) -> None:
        with self.client.get(
            "/ordenes-compra",
            headers=construir_cabeceras(token="token-invalido-locust"),
            name="P10 GET /ordenes-compra (401 token invalido)",
            catch_response=True,
        ) as resp:
            validar_error_esperado(resp, 401, "NO_AUTENTICADO")

    @tag("p10", "carga", "solo")
    @task(2)
    def rechazo_rbac_gerente_en_devoluciones_403(self) -> None:
        with self.client.get(
            "/devoluciones-proveedor",
            headers=construir_cabeceras(rol="gerente"),
            name="P10 GET /devoluciones-proveedor (403 RBAC)",
            catch_response=True,
        ) as resp:
            validar_error_esperado(resp, 403, "NO_AUTORIZADO")

    @tag("p10", "carga", "solo")
    @task(2)
    def rechazo_rbac_compras_en_aprobar_403(self) -> None:
        id_recibida = CONTEXTO["id_recibida"]
        with self.client.post(
            f"/ordenes-compra/{id_recibida}/aprobar",
            headers=construir_cabeceras(rol="compras"),
            name="P10 POST /ordenes-compra/{id}/aprobar (403 RBAC)",
            catch_response=True,
        ) as resp:
            validar_error_esperado(resp, 403, "NO_AUTORIZADO")

    @tag("p10", "carga", "solo")
    @task(2)
    def orden_inexistente_404(self) -> None:
        id_inexistente = random.randint(900000, 999999)
        with self.client.get(
            f"/ordenes-compra/{id_inexistente}",
            headers=construir_cabeceras(rol="admin"),
            name="P10 GET /ordenes-compra/{id} (404 no existe)",
            catch_response=True,
        ) as resp:
            validar_error_esperado(resp, 404, "NO_EXISTE")

    @tag("p10", "carga", "solo")
    @task(3)
    def filtros_paginacion_invalidos_422(self) -> None:
        caso = random.choice(
            (
                {"estado": "DESCONOCIDO"},
                {"per_page": 500},
                {"desde": "2026-12-31", "hasta": "2026-01-01"},
            )
        )
        with self.client.get(
            "/ordenes-compra",
            params=caso,
            headers=construir_cabeceras(rol="admin"),
            name="P10 GET /ordenes-compra (422 filtros invalidos)",
            catch_response=True,
        ) as resp:
            validar_error_esperado(resp, 422, "VALIDACION")

    @tag("p10", "carga", "solo")
    @task(3)
    def payload_creacion_invalido_422(self) -> None:
        payloads = (
            {"id_proveedor": 1, "id_bodega_destino": 1, "items": []},
            {
                "id_proveedor": 1,
                "id_bodega_destino": 1,
                "items": [
                    {"sku": "DUP-01", "cantidad": "5.000", "precio_unitario": "100.00"},
                    {"sku": "DUP-01", "cantidad": "2.000", "precio_unitario": "100.00"},
                ],
            },
            {
                "id_proveedor": True,
                "id_bodega_destino": 1,
                "items": [{"sku": "NEG-01", "cantidad": "-1", "precio_unitario": "10.00"}],
            },
        )
        with self.client.post(
            "/ordenes-compra",
            json=random.choice(payloads),
            headers=construir_cabeceras(rol="compras"),
            name="P10 POST /ordenes-compra (422 payload invalido)",
            catch_response=True,
        ) as resp:
            validar_error_esperado(resp, 422, "VALIDACION")

    @tag("p10", "carga", "solo")
    @task(3)
    def conflicto_estado_editar_o_aprobar_recibida_409(self) -> None:
        id_recibida = CONTEXTO["id_recibida"]
        if random.random() < 0.5:
            payload = {
                "id_proveedor": 1,
                "id_bodega_destino": 1,
                "items": [{"sku": "CHK-001", "cantidad": "1.000", "precio_unitario": "1000.00"}],
            }
            with self.client.put(
                f"/ordenes-compra/{id_recibida}",
                json=payload,
                headers=construir_cabeceras(rol="compras"),
                name="P10 PUT /ordenes-compra/{id} (409 no editable)",
                catch_response=True,
            ) as resp:
                validar_error_esperado(resp, 409, "ESTADO_NO_EDITABLE")
        else:
            with self.client.post(
                f"/ordenes-compra/{id_recibida}/aprobar",
                headers=construir_cabeceras(rol="gerente"),
                name="P10 POST /ordenes-compra/{id}/aprobar (409 transicion)",
                catch_response=True,
            ) as resp:
                validar_error_esperado(resp, 409, "TRANSICION_INVALIDA")

    @tag("p10", "carga", "solo")
    @task(2)
    def conflicto_anular_o_devolver_invalido_409(self) -> None:
        if random.random() < 0.5:
            id_anulada = CONTEXTO["id_anulada"]
            with self.client.post(
                f"/ordenes-compra/{id_anulada}/anular",
                json={"motivo": "Intento sobre orden ya anulada"},
                headers=construir_cabeceras(rol="gerente"),
                name="P10 POST /ordenes-compra/{id}/anular (409 transicion)",
                catch_response=True,
            ) as resp:
                validar_error_esperado(resp, 409, "TRANSICION_INVALIDA")
        else:
            id_borrador = CONTEXTO["id_borrador"]
            with self.client.post(
                f"/ordenes-compra/{id_borrador}/devoluciones",
                json={
                    "motivo": "Intento de devolucion sobre borrador",
                    "items": [{"id_detalle": 1, "cantidad": "1.000"}],
                },
                headers=construir_cabeceras(rol="jefe_bodega"),
                name="P10 POST /ordenes-compra/{id}/devoluciones (409 transicion)",
                catch_response=True,
            ) as resp:
                validar_error_esperado(resp, 409, "TRANSICION_INVALIDA")
