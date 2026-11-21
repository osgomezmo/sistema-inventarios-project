"""P04 - Prueba de Carga: Catalogo de productos suministrados (MS-Proveedores).

Tipo segun locust_test.pdf: Carga (operacion nominal sostenida sobre entidad debil).
Objetivo: Evaluar el rendimiento del catalogo `productos_suministrados` (clave primaria
compuesta `(id_proveedor, sku)` e indice `idx_productos_suministrados_sku`):
- GET /proveedores/{id}/productos (consulta del catalogo por proveedor)
- GET /proveedores?sku={sku} (subconsulta EXISTS por SKU activo)
- PUT /proveedores/{id}/productos/{sku} (upsert transaccional ON DUPLICATE KEY UPDATE)
- DELETE /proveedores/{id}/productos/{sku} (retiro limpio de SKUs temporales del usuario)

Cada usuario virtual crea un proveedor propio al iniciar (on_start) para aislar sus
escrituras PUT/DELETE y evitar contencion artificial sobre los proveedores semilla.

Parametros recomendados:
- Concurrencia: 25 usuarios | Spawn rate: 5 u/s | Duracion: 5m
- Pausa entre tareas: 0.8 a 2.0 s
- SLO objetivo: p95 < 500 ms, tasa de error < 1%
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

PAUSA = comun.leer_pausa(0.8, 2.0)


class UsuarioP04ProductosSuministrados(HttpUser):
    """Ejercita consultas, upserts transaccionales y bajas en productos_suministrados."""

    host = comun.HOST_DEFECTO
    wait_time = between(*PAUSA)

    def on_start(self) -> None:
        self.id_proveedor_propio: int | None = None
        self.skus_propios: list[str] = []
        self._asegurar_proveedor_propio()

    def _cabeceras(self, escritura: bool = False) -> dict[str, str]:
        rol = random.choice(comun.ROLES_ESCRITURA) if escritura else random.choice(comun.ROLES_LECTURA)
        return comun.construir_cabeceras(rol=rol, prefijo_correlacion="lt-p04")

    def _asegurar_proveedor_propio(self) -> int | None:
        if self.id_proveedor_propio is not None:
            return self.id_proveedor_propio
        cuerpo = comun.generar_payload_proveedor(etiqueta="P04")
        with self.client.post(
            "/proveedores",
            json=cuerpo,
            headers=self._cabeceras(escritura=True),
            name="P04 POST /proveedores (setup VU)",
            catch_response=True,
        ) as resp:
            datos = comun.validar_proveedor(resp, codigo_esperado=201)
            if datos is not None:
                self.id_proveedor_propio = int(datos["id_proveedor"])
        return self.id_proveedor_propio

    @tag("p04", "carga", "productos")
    @task(3)
    def listar_productos_proveedor(self) -> None:
        candidatos = list(comun.CONTEXTO_PROVEEDORES["ids_activos"])
        if self.id_proveedor_propio is not None:
            candidatos.append(self.id_proveedor_propio)
        id_proveedor = random.choice(candidatos)
        with self.client.get(
            f"/proveedores/{id_proveedor}/productos",
            headers=self._cabeceras(escritura=False),
            name="P04 GET /proveedores/{id}/productos",
            catch_response=True,
        ) as resp:
            datos = comun.validar_json(resp, (200,))
            if datos is not None:
                if not isinstance(datos, list):
                    resp.failure("Se esperaba lista de productos suministrados")
                else:
                    resp.success()

    @tag("p04", "carga", "productos")
    @task(2)
    def filtrar_proveedores_por_sku(self) -> None:
        bolsa_skus = self.skus_propios if self.skus_propios and random.random() < 0.4 else comun.CONTEXTO_PROVEEDORES["skus_activos"]
        sku = random.choice(bolsa_skus)
        with self.client.get(
            "/proveedores",
            params={"sku": sku, "estado": "ACTIVO", "page": 1, "per_page": 20},
            headers=self._cabeceras(escritura=False),
            name="P04 GET /proveedores?sku={sku}",
            catch_response=True,
        ) as resp:
            comun.validar_respuesta_paginada(resp)

    @tag("p04", "carga", "productos")
    @task(3)
    def upsert_producto_suministrado(self) -> None:
        id_proveedor = self._asegurar_proveedor_propio()
        if id_proveedor is None:
            return

        # Alterna entre actualizar un SKU existente (ON DUPLICATE KEY UPDATE) y registrar uno nuevo
        if self.skus_propios and (len(self.skus_propios) >= 12 or random.random() < 0.5):
            sku = random.choice(self.skus_propios)
            es_nuevo = False
        else:
            sku = comun.generar_sku_unico("LTP04")
            es_nuevo = True

        cuerpo = comun.generar_payload_producto(estado="ACTIVO")
        with self.client.put(
            f"/proveedores/{id_proveedor}/productos/{sku}",
            json=cuerpo,
            headers=self._cabeceras(escritura=True),
            name="P04 PUT /proveedores/{id}/productos/{sku}",
            catch_response=True,
        ) as resp:
            datos = comun.validar_producto(resp, codigo_esperado=200)
            if datos is not None and es_nuevo:
                self.skus_propios.append(sku)

    @tag("p04", "carga", "productos")
    @task(1)
    def eliminar_producto_temporal(self) -> None:
        id_proveedor = self._asegurar_proveedor_propio()
        if id_proveedor is None or len(self.skus_propios) <= 2:
            return
        sku = self.skus_propios.pop(0)
        with self.client.delete(
            f"/proveedores/{id_proveedor}/productos/{sku}",
            headers=self._cabeceras(escritura=True),
            name="P04 DELETE /proveedores/{id}/productos/{sku}",
            catch_response=True,
        ) as resp:
            if resp.status_code != 204:
                resp.failure(f"HTTP {resp.status_code} (esperado 204)")
            else:
                resp.success()
