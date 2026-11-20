"""P02 - Prueba de Carga: Operacion diaria mixta 80/20 (MS-Proveedores).

Tipo segun locust_test.pdf: Carga (maqueta de diapositivas 15-16: mezcla de GET
predominante y escrituras POST/PUT minoritarias con estrategia de unicidad bajo carga).
Objetivo: Validar SLAs bajo el perfil realista de operacion del supermercado (~82%
consultas de lectura y ~18% altas/actualizaciones de proveedores con NIT DIAN valido).

Parametros recomendados:
- Concurrencia: 30 usuarios | Spawn rate: 5 u/s | Duracion: 5m (10-30m en corrida formal)
- Pausa entre tareas: 1.0 a 3.0 s
- SLO objetivo: p95 < 500 ms, tasa de error < 1% (409 NIT duplicado cuenta como fallo)
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

_DIR_ACTUAL = str(Path(__file__).resolve().parent)
if _DIR_ACTUAL not in sys.path:
    sys.path.insert(0, _DIR_ACTUAL)

from locust import HttpUser, between, tag, task

import comun

PAUSA = comun.leer_pausa(1.0, 3.0)


class UsuarioP02CargaMixta(HttpUser):
    """Mezcla realista de 82% lecturas GET y 18% escrituras POST/PUT sobre proveedores."""

    host = comun.HOST_DEFECTO
    wait_time = between(*PAUSA)

    def on_start(self) -> None:
        self.ids_creados: list[int] = []

    def _cabeceras(self, escritura: bool = False) -> dict[str, str]:
        rol = random.choice(comun.ROLES_ESCRITURA) if escritura else random.choice(comun.ROLES_LECTURA)
        return comun.construir_cabeceras(rol=rol, prefijo_correlacion="lt-p02")

    @tag("p02", "carga", "mixta")
    @task(4)
    def listar_proveedores(self) -> None:
        params = {"page": 1, "per_page": 20, "estado": "ACTIVO"}
        with self.client.get(
            "/proveedores",
            params=params,
            headers=self._cabeceras(escritura=False),
            name="P02 GET /proveedores",
            catch_response=True,
        ) as resp:
            comun.validar_respuesta_paginada(resp)

    @tag("p02", "carga", "mixta")
    @task(3)
    def consultar_proveedor_por_id(self) -> None:
        candidatos = self.ids_creados[-5:] if self.ids_creados else comun.CONTEXTO_PROVEEDORES["ids_todos"]
        id_proveedor = random.choice(candidatos)
        with self.client.get(
            f"/proveedores/{id_proveedor}",
            headers=self._cabeceras(escritura=False),
            name="P02 GET /proveedores/{id}",
            catch_response=True,
        ) as resp:
            comun.validar_proveedor(resp, codigo_esperado=200)

    @tag("p02", "carga", "mixta")
    @task(2)
    def consultar_productos_proveedor(self) -> None:
        id_proveedor = random.choice(comun.CONTEXTO_PROVEEDORES["ids_activos"])
        with self.client.get(
            f"/proveedores/{id_proveedor}/productos",
            headers=self._cabeceras(escritura=False),
            name="P02 GET /proveedores/{id}/productos",
            catch_response=True,
        ) as resp:
            datos = comun.validar_json(resp, (200,))
            if datos is not None:
                if not isinstance(datos, list):
                    resp.failure("Se esperaba una lista JSON de productos")
                else:
                    resp.success()

    @tag("p02", "carga", "mixta")
    @task(1)
    def crear_proveedor_nuevo(self) -> None:
        cuerpo = comun.generar_payload_proveedor(etiqueta="P02", incluir_contactos=True)
        with self.client.post(
            "/proveedores",
            json=cuerpo,
            headers=self._cabeceras(escritura=True),
            name="P02 POST /proveedores",
            catch_response=True,
        ) as resp:
            datos = comun.validar_proveedor(resp, codigo_esperado=201)
            if datos is not None:
                self.ids_creados.append(int(datos["id_proveedor"]))
                if len(self.ids_creados) > 20:
                    self.ids_creados.pop(0)

    @tag("p02", "carga", "mixta")
    @task(1)
    def actualizar_proveedor_propio(self) -> None:
        if not self.ids_creados:
            self.crear_proveedor_nuevo()
            return
        id_proveedor = random.choice(self.ids_creados)
        cuerpo = comun.generar_payload_actualizacion_proveedor(etiqueta="P02")
        with self.client.put(
            f"/proveedores/{id_proveedor}",
            json=cuerpo,
            headers=self._cabeceras(escritura=True),
            name="P02 PUT /proveedores/{id}",
            catch_response=True,
        ) as resp:
            comun.validar_proveedor(resp, codigo_esperado=200)
