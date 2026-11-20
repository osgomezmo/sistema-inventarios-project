"""P05 - Prueba de Estres: Busqueda con filtros y lecturas bajo rampa agresiva (MS-Proveedores).

Tipo segun locust_test.pdf: Estres (incremento progresivo mas alla del diseno nominal).
Objetivo: Identificar el punto de degradacion y quiebre (latencia p95, timeouts, 5xx)
al escalar concurrencia sobre consultas intensivas en MySQL (filtros LIKE sobre nit y
razon_social, subconsultas EXISTS por SKU, paginacion con JOIN/IN de contactos y detalle).
Registra concurrencia y RPS al superar el 5% de errores o alcanzar el techo de 200 usuarios.

Perfil LoadTestShape por defecto (sobreescribible por LT_PASO_USUARIOS, LT_PASO_SEGUNDOS,
LT_MAX_USUARIOS y LT_LIMITE_ERRORES):
- Rampa escalonada: 20 -> 200 usuarios, +20 usuarios cada 30 s (10 escalones = 5m max)
- Pausa entre tareas: 0.3 a 1.0 s
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

PAUSA = comun.leer_pausa(0.3, 1.0)


class UsuarioP05EstresBusquedas(HttpUser):
    """Genera alta concurrencia de busquedas LIKE/EXISTS y lecturas detalladas."""

    host = comun.HOST_DEFECTO
    wait_time = between(*PAUSA)

    def _cabeceras(self) -> dict[str, str]:
        return comun.construir_cabeceras(
            rol=random.choice(comun.ROLES_LECTURA),
            prefijo_correlacion="lt-p05",
        )

    @tag("p05", "estres", "lectura")
    @task(4)
    def busqueda_like_nit_o_razon_social(self) -> None:
        termino = random.choice(comun.TERMINOS_BUSQUEDA)
        per_page = random.choice((20, 50, 100))
        with self.client.get(
            "/proveedores",
            params={"q": termino, "page": 1, "per_page": per_page},
            headers=self._cabeceras(),
            name="P05 GET /proveedores?q={termino}",
            catch_response=True,
        ) as resp:
            comun.validar_respuesta_paginada(resp)

    @tag("p05", "estres", "lectura")
    @task(3)
    def busqueda_exists_por_sku(self) -> None:
        sku = random.choice(comun.CONTEXTO_PROVEEDORES["skus_activos"])
        with self.client.get(
            "/proveedores",
            params={"sku": sku, "estado": "ACTIVO", "page": 1, "per_page": 50},
            headers=self._cabeceras(),
            name="P05 GET /proveedores?sku={sku}",
            catch_response=True,
        ) as resp:
            comun.validar_respuesta_paginada(resp)

    @tag("p05", "estres", "lectura")
    @task(2)
    def detalle_proveedor_con_contactos(self) -> None:
        id_proveedor = random.choice(comun.CONTEXTO_PROVEEDORES["ids_todos"])
        with self.client.get(
            f"/proveedores/{id_proveedor}",
            headers=self._cabeceras(),
            name="P05 GET /proveedores/{id}",
            catch_response=True,
        ) as resp:
            comun.validar_proveedor(resp, codigo_esperado=200)

    @tag("p05", "estres", "lectura")
    @task(2)
    def catalogo_productos_por_proveedor(self) -> None:
        id_proveedor = random.choice(comun.CONTEXTO_PROVEEDORES["ids_activos"])
        with self.client.get(
            f"/proveedores/{id_proveedor}/productos",
            headers=self._cabeceras(),
            name="P05 GET /proveedores/{id}/productos",
            catch_response=True,
        ) as resp:
            datos = comun.validar_json(resp, (200,))
            if datos is not None:
                if not isinstance(datos, list):
                    resp.failure("Se esperaba arreglo de productos")
                else:
                    resp.success()


FormaEstresP05 = comun.crear_forma_estres(
    nombre_clase="FormaEstresP05",
    paso_usuarios_defecto=20,
    paso_segundos_defecto=30,
    maximo_usuarios_defecto=200,
    limite_errores_defecto=0.05,
)
