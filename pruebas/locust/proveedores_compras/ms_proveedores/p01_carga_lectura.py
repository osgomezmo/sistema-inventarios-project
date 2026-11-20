"""P01 - Prueba de Carga: Lectura nominal del catalogo de proveedores (MS-Proveedores).

Tipo segun locust_test.pdf: Carga (comportamiento nominal sostenido en meseta).
Objetivo: Verificar cumplimiento de SLAs en consultas de solo lectura del maestro de
proveedores (listado paginado, filtros por estado/texto/SKU, detalle con contactos,
productos suministrados y sonda de disponibilidad /health/ready).

Parametros recomendados:
- Concurrencia: 25 usuarios | Spawn rate: 5 u/s | Duracion: 5m (10-30m en corrida formal)
- Pausa entre tareas: 1.0 a 3.0 s
- SLO objetivo: p95 < 300 ms, tasa de error < 1%
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


class UsuarioP01CargaLectura(HttpUser):
    """Simula clientes de consulta (gateway, compras, bodega, gerencia) sobre MS-Proveedores."""

    host = comun.HOST_DEFECTO
    wait_time = between(*PAUSA)

    def _cabeceras_lectura(self) -> dict[str, str]:
        return comun.construir_cabeceras(
            rol=random.choice(comun.ROLES_LECTURA),
            prefijo_correlacion="lt-p01",
        )

    @tag("p01", "carga", "lectura")
    @task(4)
    def listar_proveedores_paginado(self) -> None:
        per_page = random.choice((10, 20, 50))
        params = {"page": 1, "per_page": per_page, "estado": "ACTIVO"}
        with self.client.get(
            "/proveedores",
            params=params,
            headers=self._cabeceras_lectura(),
            name="P01 GET /proveedores?estado=ACTIVO",
            catch_response=True,
        ) as resp:
            comun.validar_respuesta_paginada(resp)

    @tag("p01", "carga", "lectura")
    @task(3)
    def obtener_detalle_proveedor(self) -> None:
        id_proveedor = random.choice(comun.CONTEXTO_PROVEEDORES["ids_todos"])
        with self.client.get(
            f"/proveedores/{id_proveedor}",
            headers=self._cabeceras_lectura(),
            name="P01 GET /proveedores/{id}",
            catch_response=True,
        ) as resp:
            comun.validar_proveedor(resp, codigo_esperado=200)

    @tag("p01", "carga", "lectura")
    @task(2)
    def listar_productos_de_proveedor(self) -> None:
        id_proveedor = random.choice(comun.CONTEXTO_PROVEEDORES["ids_activos"])
        with self.client.get(
            f"/proveedores/{id_proveedor}/productos",
            headers=self._cabeceras_lectura(),
            name="P01 GET /proveedores/{id}/productos",
            catch_response=True,
        ) as resp:
            datos = comun.validar_json(resp, (200,))
            if datos is not None:
                if not isinstance(datos, list):
                    resp.failure("Se esperaba una lista JSON de productos suministrados")
                else:
                    resp.success()

    @tag("p01", "carga", "lectura")
    @task(2)
    def buscar_por_texto_o_sku(self) -> None:
        if random.random() < 0.5:
            termino = random.choice(comun.TERMINOS_BUSQUEDA)
            params = {"q": termino, "page": 1, "per_page": 20}
            nombre = "P01 GET /proveedores?q={termino}"
        else:
            sku = random.choice(comun.CONTEXTO_PROVEEDORES["skus_activos"])
            params = {"sku": sku, "estado": "ACTIVO", "page": 1, "per_page": 20}
            nombre = "P01 GET /proveedores?sku={sku}"

        with self.client.get(
            "/proveedores",
            params=params,
            headers=self._cabeceras_lectura(),
            name=nombre,
            catch_response=True,
        ) as resp:
            comun.validar_respuesta_paginada(resp)

    @tag("p01", "carga", "lectura")
    @task(1)
    def verificar_salud_db(self) -> None:
        with self.client.get(
            "/health/ready",
            name="P01 GET /health/ready",
            catch_response=True,
        ) as resp:
            datos = comun.validar_json(resp, (200,))
            if datos is not None:
                if datos.get("status") != "ok" or datos.get("db") != "connected":
                    resp.failure(f"Estado de salud inesperado: {datos}")
                else:
                    resp.success()
