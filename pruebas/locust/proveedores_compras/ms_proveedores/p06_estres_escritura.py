"""P06 - Prueba de Estres: Escrituras transaccionales concurrentes (MS-Proveedores).

Tipo segun locust_test.pdf: Estres (rampa agresiva hasta degradacion/quiebre).
Objetivo: Llevar al limite la capacidad de escritura concurrente de MS-Proveedores y su
pool de conexiones MySQL (`connectionLimit: 10`, MySQL 8.4 `--max-connections=50`,
`--innodb-buffer-pool-size=32M`), combinando transacciones multi-tabla en POST /proveedores,
upserts transaccionales en productos_suministrados, altas de contactos y actualizaciones PUT.

Perfil LoadTestShape por defecto:
- Rampa escalonada: 15 -> 150 usuarios, +15 usuarios cada 30 s (10 escalones = 5m max)
- Pausa entre tareas: 0.2 a 0.8 s
- Criterio de corte automatico: tasa de error > 5% (tras minimo 20 peticiones)
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

PAUSA = comun.leer_pausa(0.2, 0.8)


class UsuarioP06EstresEscrituras(HttpUser):
    """Somete a estres las transacciones de escritura InnoDB y el pool de conexiones."""

    host = comun.HOST_DEFECTO
    wait_time = between(*PAUSA)

    def on_start(self) -> None:
        self.ids_propios: list[int] = []

    def _cabeceras(self) -> dict[str, str]:
        return comun.construir_cabeceras(
            rol=random.choice(comun.ROLES_ESCRITURA),
            prefijo_correlacion="lt-p06",
        )

    @tag("p06", "estres", "escritura")
    @task(4)
    def crear_proveedor_transaccional(self) -> None:
        cuerpo = comun.generar_payload_proveedor(
            etiqueta="P06",
            incluir_contactos=True,
            incluir_productos=True,
        )
        with self.client.post(
            "/proveedores",
            json=cuerpo,
            headers=self._cabeceras(),
            name="P06 POST /proveedores (transaccional)",
            catch_response=True,
        ) as resp:
            datos = comun.validar_proveedor(resp, codigo_esperado=201)
            if datos is not None:
                self.ids_propios.append(int(datos["id_proveedor"]))
                if len(self.ids_propios) > 15:
                    self.ids_propios.pop(0)

    @tag("p06", "estres", "escritura")
    @task(3)
    def upsert_producto_concurrente(self) -> None:
        if not self.ids_propios:
            self.crear_proveedor_transaccional()
            return
        id_proveedor = random.choice(self.ids_propios)
        sku = comun.generar_sku_unico("LTP06")
        cuerpo = comun.generar_payload_producto(estado="ACTIVO")
        with self.client.put(
            f"/proveedores/{id_proveedor}/productos/{sku}",
            json=cuerpo,
            headers=self._cabeceras(),
            name="P06 PUT /proveedores/{id}/productos/{sku}",
            catch_response=True,
        ) as resp:
            comun.validar_producto(resp, codigo_esperado=200)

    @tag("p06", "estres", "escritura")
    @task(2)
    def crear_contacto_concurrente(self) -> None:
        if not self.ids_propios:
            self.crear_proveedor_transaccional()
            return
        id_proveedor = random.choice(self.ids_propios)
        cuerpo = comun.generar_payload_contacto(etiqueta="P06")
        with self.client.post(
            f"/proveedores/{id_proveedor}/contactos",
            json=cuerpo,
            headers=self._cabeceras(),
            name="P06 POST /proveedores/{id}/contactos",
            catch_response=True,
        ) as resp:
            comun.validar_contacto(resp, codigo_esperado=201)

    @tag("p06", "estres", "escritura")
    @task(2)
    def actualizar_proveedor_concurrente(self) -> None:
        if not self.ids_propios:
            self.crear_proveedor_transaccional()
            return
        id_proveedor = random.choice(self.ids_propios)
        cuerpo = comun.generar_payload_actualizacion_proveedor(etiqueta="P06")
        with self.client.put(
            f"/proveedores/{id_proveedor}",
            json=cuerpo,
            headers=self._cabeceras(),
            name="P06 PUT /proveedores/{id}",
            catch_response=True,
        ) as resp:
            comun.validar_proveedor(resp, codigo_esperado=200)

    @tag("p06", "estres", "escritura")
    @task(1)
    def verificar_lectura_post_escritura(self) -> None:
        candidatos = self.ids_propios or comun.CONTEXTO_PROVEEDORES["ids_activos"]
        id_proveedor = random.choice(candidatos)
        with self.client.get(
            f"/proveedores/{id_proveedor}",
            headers=self._cabeceras(),
            name="P06 GET /proveedores/{id}",
            catch_response=True,
        ) as resp:
            comun.validar_proveedor(resp, codigo_esperado=200)


FormaEstresP06 = comun.crear_forma_estres(
    nombre_clase="FormaEstresP06",
    paso_usuarios_defecto=15,
    paso_segundos_defecto=30,
    maximo_usuarios_defecto=150,
    limite_errores_defecto=0.05,
)
