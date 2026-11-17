"""Pruebas de rendimiento del bloque B (inventario), todas a través del gateway.

B1 GET /api/stock/{sku}           B2 GET /api/stock?bajo_minimo=true
B3 POST /api/movimientos (SALIDA) B4 POST /api/traslados
B5 GET /api/kardex

Cada prueba se corre sola con su etiqueta (--tags b1 ... b5); ejecutar.sh fija
los parámetros de cada escenario. El token se obtiene UNA vez en test_start con
el usuario de pruebas/locust/.env y lo comparten todos los usuarios virtuales
(el login del gateway admite 5 intentos por minuto). Cualquier respuesta que no
sea la esperada, incluido un 409, cuenta como error.
"""

import os
import random
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from locust import HttpUser, between, events, tag, task

AQUI = Path(__file__).resolve().parent
SKUS = [f"LT-{n:04d}" for n in range(1, 2001)]
SKUS_GRANDES = SKUS[:50]  # con saldo grande en LT-B1 y LT-B2
SKU_KARDEX = "LT-0001"
PAUSA = (float(os.getenv("LT_PAUSA_MIN", "1")), float(os.getenv("LT_PAUSA_MAX", "3")))

contexto = {"token": None, "bodegas": {}}


def leer_env(ruta):
    valores = {}
    if ruta.exists():
        for linea in ruta.read_text().splitlines():
            if "=" in linea and not linea.lstrip().startswith("#"):
                clave, valor = linea.split("=", 1)
                valores[clave.strip()] = valor.strip()
    return valores


@events.test_start.add_listener
def iniciar(environment, **_):
    """Inicia sesión una sola vez y busca los ids de las bodegas LT."""
    env = leer_env(AQUI / ".env")
    if not env.get("LT_EMAIL") or not env.get("LT_PASSWORD"):
        raise SystemExit("Falta pruebas/locust/.env: ejecuta preparar_datos.py")
    host = environment.host
    r = requests.post(f"{host}/api/auth/login",
                      json={"email": env["LT_EMAIL"], "password": env["LT_PASSWORD"]}, timeout=10)
    if r.status_code != 200:
        raise SystemExit(f"No se pudo iniciar sesión con el usuario de prueba: HTTP {r.status_code}")
    contexto["token"] = r.json()["token"]
    cabeceras = {"Authorization": f"Bearer {contexto['token']}"}
    bodegas = requests.get(f"{host}/api/bodegas", params={"per_page": 100}, headers=cabeceras, timeout=10)
    contexto["bodegas"] = {b["codigo"]: b["id_bodega"] for b in bodegas.json()["data"]
                           if b["codigo"].startswith("LT-")}
    if not {"LT-B1", "LT-B2"} <= set(contexto["bodegas"]):
        raise SystemExit("Faltan las bodegas LT-B1 y LT-B2: ejecuta preparar_datos.py")


@events.test_stop.add_listener
def terminar(environment, **_):
    """Revoca el token de la corrida."""
    if contexto["token"]:
        requests.post(f"{environment.host}/api/auth/logout",
                      headers={"Authorization": f"Bearer {contexto['token']}"}, timeout=10)
        contexto["token"] = None


class UsuarioBodega(HttpUser):
    wait_time = between(*PAUSA)

    def on_start(self):
        self.b1 = contexto["bodegas"]["LT-B1"]
        self.b2 = contexto["bodegas"]["LT-B2"]
        self.hacia_b2 = random.random() < 0.5  # sentido inicial del traslado

    def cabeceras(self):
        return {"Authorization": f"Bearer {contexto['token']}", "X-Correlation-Id": f"lt-{uuid.uuid4()}"}

    @tag("b1")
    @task
    def b1_stock_por_sku(self):
        self.client.get(f"/api/stock/{random.choice(SKUS)}", headers=self.cabeceras(),
                        name="B1 GET /api/stock/{sku}")

    @tag("b2")
    @task
    def b2_stock_bajo_minimo(self):
        self.client.get("/api/stock", params={"bajo_minimo": "true"}, headers=self.cabeceras(),
                        name="B2 GET /api/stock?bajo_minimo=true")

    @tag("b3")
    @task
    def b3_salida(self):
        cuerpo = {"sku": random.choice(SKUS_GRANDES), "id_bodega": random.choice((self.b1, self.b2)),
                  "tipo": "SALIDA", "cantidad": 1, "motivo": "Prueba de rendimiento LT"}
        with self.client.post("/api/movimientos", json=cuerpo, headers=self.cabeceras(),
                              name="B3 POST /api/movimientos", catch_response=True) as r:
            if r.status_code != 201:
                r.failure(f"HTTP {r.status_code}")

    @tag("b4")
    @task
    def b4_traslado(self):
        origen, destino = (self.b1, self.b2) if self.hacia_b2 else (self.b2, self.b1)
        self.hacia_b2 = not self.hacia_b2  # alterna el sentido
        cuerpo = {"sku": random.choice(SKUS_GRANDES), "id_bodega_origen": origen,
                  "id_bodega_destino": destino, "cantidad": 1, "motivo": "Prueba de rendimiento LT"}
        with self.client.post("/api/traslados", json=cuerpo, headers=self.cabeceras(),
                              name="B4 POST /api/traslados", catch_response=True) as r:
            if r.status_code != 201:
                r.failure(f"HTTP {r.status_code}")

    @tag("b5")
    @task
    def b5_kardex(self):
        hoy = datetime.now(ZoneInfo("America/Bogota")).date().isoformat()
        self.client.get("/api/kardex", params={"sku": SKU_KARDEX, "id_bodega": self.b1, "desde": hoy, "hasta": hoy},
                        headers=self.cabeceras(), name="B5 GET /api/kardex")
