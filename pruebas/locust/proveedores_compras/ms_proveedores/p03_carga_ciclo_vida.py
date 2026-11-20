"""P03 - Prueba de Carga: Ciclo de vida completo de proveedor y contactos (MS-Proveedores).

Tipo segun locust_test.pdf: Carga (flujo transaccional stateful en meseta sostenida).
Objetivo: Ejercitar de extremo a extremo todas las operaciones del ciclo de vida de un
proveedor y sus contactos sin alterar los proveedores sembrados:
  1. POST /proveedores (con contacto y producto inicial en transaccion MySQL)
  2. GET /proveedores/{id}
  3. PUT /proveedores/{id}
  4. POST /proveedores/{id}/contactos
  5. PUT /proveedores/{id}/contactos/{id_contacto}
  6. POST /proveedores/{id}/inactivar
  7. POST /proveedores/{id}/activar
  8. DELETE /proveedores/{id}/contactos/{id_contacto}

Parametros recomendados:
- Concurrencia: 20 usuarios | Spawn rate: 4 u/s | Duracion: 5m
- Pausa entre pasos: 1.0 a 2.5 s
- SLO objetivo: p95 < 600 ms, tasa de error < 1%
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

_DIR_ACTUAL = str(Path(__file__).resolve().parent)
if _DIR_ACTUAL not in sys.path:
    sys.path.insert(0, _DIR_ACTUAL)

from locust import HttpUser, SequentialTaskSet, between, tag, task

import comun

PAUSA = comun.leer_pausa(1.0, 2.5)


class FlujoCicloVidaProveedor(SequentialTaskSet):
    """Secuencia ordenada de CRUD completo y transiciones de estado para un proveedor."""

    def on_start(self) -> None:
        self.id_proveedor: int | None = None
        self.id_contacto: int | None = None

    def _cabeceras(self) -> dict[str, str]:
        return comun.construir_cabeceras(
            rol=random.choice(comun.ROLES_ESCRITURA),
            prefijo_correlacion="lt-p03",
        )

    @task
    def paso_1_crear_proveedor(self) -> None:
        self.id_proveedor = None
        self.id_contacto = None
        cuerpo = comun.generar_payload_proveedor(
            etiqueta="P03",
            incluir_contactos=True,
            incluir_productos=True,
        )
        with self.client.post(
            "/proveedores",
            json=cuerpo,
            headers=self._cabeceras(),
            name="P03 POST /proveedores (transaccional)",
            catch_response=True,
        ) as resp:
            datos = comun.validar_proveedor(resp, codigo_esperado=201)
            if datos is not None:
                self.id_proveedor = int(datos["id_proveedor"])

    @task
    def paso_2_consultar_detalle(self) -> None:
        if self.id_proveedor is None:
            return
        with self.client.get(
            f"/proveedores/{self.id_proveedor}",
            headers=self._cabeceras(),
            name="P03 GET /proveedores/{id}",
            catch_response=True,
        ) as resp:
            comun.validar_proveedor(resp, codigo_esperado=200)

    @task
    def paso_3_actualizar_proveedor(self) -> None:
        if self.id_proveedor is None:
            return
        cuerpo = comun.generar_payload_actualizacion_proveedor(etiqueta="P03")
        with self.client.put(
            f"/proveedores/{self.id_proveedor}",
            json=cuerpo,
            headers=self._cabeceras(),
            name="P03 PUT /proveedores/{id}",
            catch_response=True,
        ) as resp:
            comun.validar_proveedor(resp, codigo_esperado=200)

    @task
    def paso_4_crear_contacto(self) -> None:
        if self.id_proveedor is None:
            return
        cuerpo = comun.generar_payload_contacto(etiqueta="P03")
        with self.client.post(
            f"/proveedores/{self.id_proveedor}/contactos",
            json=cuerpo,
            headers=self._cabeceras(),
            name="P03 POST /proveedores/{id}/contactos",
            catch_response=True,
        ) as resp:
            datos = comun.validar_contacto(resp, codigo_esperado=201)
            if datos is not None:
                self.id_contacto = int(datos["id_contacto"])

    @task
    def paso_5_actualizar_contacto(self) -> None:
        if self.id_proveedor is None or self.id_contacto is None:
            return
        cuerpo = comun.generar_payload_contacto(etiqueta="P03-UPD")
        with self.client.put(
            f"/proveedores/{self.id_proveedor}/contactos/{self.id_contacto}",
            json=cuerpo,
            headers=self._cabeceras(),
            name="P03 PUT /proveedores/{id}/contactos/{id_contacto}",
            catch_response=True,
        ) as resp:
            comun.validar_contacto(resp, codigo_esperado=200)

    @task
    def paso_6_inactivar_proveedor(self) -> None:
        if self.id_proveedor is None:
            return
        with self.client.post(
            f"/proveedores/{self.id_proveedor}/inactivar",
            headers=self._cabeceras(),
            name="P03 POST /proveedores/{id}/inactivar",
            catch_response=True,
        ) as resp:
            datos = comun.validar_proveedor(resp, codigo_esperado=200)
            if datos is not None and datos.get("estado") != "INACTIVO":
                resp.failure(f"Estado esperado INACTIVO, recibido {datos.get('estado')}")

    @task
    def paso_7_activar_proveedor(self) -> None:
        if self.id_proveedor is None:
            return
        with self.client.post(
            f"/proveedores/{self.id_proveedor}/activar",
            headers=self._cabeceras(),
            name="P03 POST /proveedores/{id}/activar",
            catch_response=True,
        ) as resp:
            datos = comun.validar_proveedor(resp, codigo_esperado=200)
            if datos is not None and datos.get("estado") != "ACTIVO":
                resp.failure(f"Estado esperado ACTIVO, recibido {datos.get('estado')}")

    @task
    def paso_8_eliminar_contacto(self) -> None:
        if self.id_proveedor is None or self.id_contacto is None:
            return
        with self.client.delete(
            f"/proveedores/{self.id_proveedor}/contactos/{self.id_contacto}",
            headers=self._cabeceras(),
            name="P03 DELETE /proveedores/{id}/contactos/{id_contacto}",
            catch_response=True,
        ) as resp:
            if resp.status_code != 204:
                resp.failure(f"HTTP {resp.status_code} (esperado 204)")
            else:
                resp.success()
                self.id_contacto = None


@tag("p03", "carga", "ciclo_vida")
class UsuarioP03CicloVidaContactos(HttpUser):
    """Ejecuta el ciclo de vida completo de alta, edicion, contactos y estado."""

    host = comun.HOST_DEFECTO
    wait_time = between(*PAUSA)
    tasks = [FlujoCicloVidaProveedor]
