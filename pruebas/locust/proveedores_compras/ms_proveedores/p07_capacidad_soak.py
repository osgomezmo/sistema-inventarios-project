"""P07 - Prueba de Capacidad (Soak): Resistencia sostenida en el tiempo (MS-Proveedores).

Tipo segun locust_test.pdf: Capacidad (soak) — carga alta sostenida cercana al maximo
estable (NO al quiebre) durante un periodo prolongado (diapositivas 7 y 16).
Objetivo: Detectar degradacion gradual en el tiempo: fugas de memoria en Node.js/Express,
agotamiento o latencia creciente en el pool de conexiones mysql2 (`connectionLimit: 10`),
saturacion de I/O en MySQL 8.4 y deriva temporal de p95/RPS.

Mantiene un volumen controlado de datos temporales por usuario virtual (crea/elimina
contactos y recicla SKUs temporales) para que la prueba pueda sostenerse 60 minutos o mas
sin degradar artificialmente la base de datos por crecimiento desmedido.

Parametros recomendados:
- Concurrencia: 40 usuarios (cercano al maximo estable) | Spawn rate: 5 u/s
- Duracion: 15m en validacion local / 60m (LT_DURACION=60m) en corrida soak formal
- Pausa entre tareas: 1.0 a 2.5 s
- SLO objetivo: p95 < 700 ms, deriva temporal de p95 < 20%, tasa de error < 1%
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

PAUSA = comun.leer_pausa(1.0, 2.5)


class UsuarioP07CapacidadSoak(HttpUser):
    """Carga alta sostenida y equilibrada para analisis de estabilidad longitudinal."""

    host = comun.HOST_DEFECTO
    wait_time = between(*PAUSA)

    def on_start(self) -> None:
        self.id_proveedor_propio: int | None = None
        self.skus_temporales: list[str] = []
        self._asegurar_proveedor_propio()

    def _cabeceras(self, escritura: bool = False) -> dict[str, str]:
        rol = random.choice(comun.ROLES_ESCRITURA) if escritura else random.choice(comun.ROLES_LECTURA)
        return comun.construir_cabeceras(rol=rol, prefijo_correlacion="lt-p07")

    def _asegurar_proveedor_propio(self) -> int | None:
        if self.id_proveedor_propio is not None:
            return self.id_proveedor_propio
        cuerpo = comun.generar_payload_proveedor(etiqueta="P07", incluir_contactos=True)
        with self.client.post(
            "/proveedores",
            json=cuerpo,
            headers=self._cabeceras(escritura=True),
            name="P07 POST /proveedores (setup VU)",
            catch_response=True,
        ) as resp:
            datos = comun.validar_proveedor(resp, codigo_esperado=201)
            if datos is not None:
                self.id_proveedor_propio = int(datos["id_proveedor"])
        return self.id_proveedor_propio

    @tag("p07", "capacidad", "soak")
    @task(5)
    def listar_catalogo_paginado(self) -> None:
        params: dict[str, object] = {"page": 1, "per_page": 20, "estado": "ACTIVO"}
        if random.random() < 0.35:
            params["q"] = random.choice(comun.TERMINOS_BUSQUEDA)
        with self.client.get(
            "/proveedores",
            params=params,
            headers=self._cabeceras(escritura=False),
            name="P07 GET /proveedores",
            catch_response=True,
        ) as resp:
            comun.validar_respuesta_paginada(resp)

    @tag("p07", "capacidad", "soak")
    @task(4)
    def consultar_detalle_proveedor(self) -> None:
        candidatos = list(comun.CONTEXTO_PROVEEDORES["ids_todos"])
        if self.id_proveedor_propio is not None:
            candidatos.append(self.id_proveedor_propio)
        id_proveedor = random.choice(candidatos)
        with self.client.get(
            f"/proveedores/{id_proveedor}",
            headers=self._cabeceras(escritura=False),
            name="P07 GET /proveedores/{id}",
            catch_response=True,
        ) as resp:
            comun.validar_proveedor(resp, codigo_esperado=200)

    @tag("p07", "capacidad", "soak")
    @task(3)
    def consultar_productos_proveedor(self) -> None:
        id_proveedor = random.choice(comun.CONTEXTO_PROVEEDORES["ids_activos"])
        with self.client.get(
            f"/proveedores/{id_proveedor}/productos",
            headers=self._cabeceras(escritura=False),
            name="P07 GET /proveedores/{id}/productos",
            catch_response=True,
        ) as resp:
            datos = comun.validar_json(resp, (200,))
            if datos is not None:
                if not isinstance(datos, list):
                    resp.failure("Se esperaba una lista de productos")
                else:
                    resp.success()

    @tag("p07", "capacidad", "soak")
    @task(2)
    def upsert_y_reciclaje_producto(self) -> None:
        id_proveedor = self._asegurar_proveedor_propio()
        if id_proveedor is None:
            return
        if len(self.skus_temporales) < 5:
            sku = comun.generar_sku_unico("LTP07")
            self.skus_temporales.append(sku)
        else:
            sku = random.choice(self.skus_temporales)

        cuerpo = comun.generar_payload_producto(estado="ACTIVO")
        with self.client.put(
            f"/proveedores/{id_proveedor}/productos/{sku}",
            json=cuerpo,
            headers=self._cabeceras(escritura=True),
            name="P07 PUT /proveedores/{id}/productos/{sku}",
            catch_response=True,
        ) as resp:
            comun.validar_producto(resp, codigo_esperado=200)

    @tag("p07", "capacidad", "soak")
    @task(1)
    def ciclo_corto_contacto_con_limpieza(self) -> None:
        """Crea y elimina un contacto temporal para ejercitar escritura sin inflar la tabla."""
        id_proveedor = self._asegurar_proveedor_propio()
        if id_proveedor is None:
            return

        cuerpo = comun.generar_payload_contacto(etiqueta="P07")
        id_contacto: int | None = None
        with self.client.post(
            f"/proveedores/{id_proveedor}/contactos",
            json=cuerpo,
            headers=self._cabeceras(escritura=True),
            name="P07 POST /proveedores/{id}/contactos",
            catch_response=True,
        ) as resp:
            datos = comun.validar_contacto(resp, codigo_esperado=201)
            if datos is not None:
                id_contacto = int(datos["id_contacto"])

        if id_contacto is not None:
            with self.client.delete(
                f"/proveedores/{id_proveedor}/contactos/{id_contacto}",
                headers=self._cabeceras(escritura=True),
                name="P07 DELETE /proveedores/{id}/contactos/{id_contacto}",
                catch_response=True,
            ) as resp:
                if resp.status_code != 204:
                    resp.failure(f"HTTP {resp.status_code} (esperado 204)")
                else:
                    resp.success()

    @tag("p07", "capacidad", "soak")
    @task(1)
    def actualizar_proveedor_propio(self) -> None:
        id_proveedor = self._asegurar_proveedor_propio()
        if id_proveedor is None:
            return
        cuerpo = comun.generar_payload_actualizacion_proveedor(etiqueta="P07")
        with self.client.put(
            f"/proveedores/{id_proveedor}",
            json=cuerpo,
            headers=self._cabeceras(escritura=True),
            name="P07 PUT /proveedores/{id}",
            catch_response=True,
        ) as resp:
            comun.validar_proveedor(resp, codigo_esperado=200)

    @tag("p07", "capacidad", "soak")
    @task(1)
    def sonda_salud_continua(self) -> None:
        ruta = "/health/ready" if random.random() < 0.7 else "/health"
        with self.client.get(
            ruta,
            name=f"P07 GET {ruta}",
            catch_response=True,
        ) as resp:
            datos = comun.validar_json(resp, (200,))
            if datos is not None:
                if datos.get("status") != "ok":
                    resp.failure(f"Estado de salud inesperado: {datos}")
                else:
                    resp.success()
