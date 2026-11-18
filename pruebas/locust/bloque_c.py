"""Pruebas de rendimiento del bloque C (Reportes y Notificaciones), a través del API Gateway.

C1 GET /api/dashboard
C2 GET /api/reportes/valorizacion (JSON)
C3 GET /api/reportes/valorizacion?formato=csv (CSV)
C4 GET /api/reportes/rotacion
C5 GET /api/reportes/stock-bajo
C6 POST /api/dispositivos
C7 GET /api/notificaciones

Cada prueba puede ejecutarse individualmente con su etiqueta (--tags c1 ... c7)
o todas juntas. El token Sanctum se obtiene en test_start y lo comparten los usuarios virtuales.
"""

import os
import random
import uuid
from pathlib import Path

import requests
from locust import HttpUser, between, events, tag, task

AQUI = Path(__file__).resolve().parent
PAUSA = (float(os.getenv("LT_PAUSA_MIN", "1")), float(os.getenv("LT_PAUSA_MAX", "3")))

contexto = {"token": None}


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
    """Inicia sesión una sola vez para obtener el token de servicio o usuario."""
    env = leer_env(AQUI / ".env")
    email = env.get("LT_EMAIL") or os.getenv("ADMIN_EMAIL", "admin@inventario.local")
    password = env.get("LT_PASSWORD") or os.getenv("ADMIN_PASSWORD", "Inventario2026")
    host = environment.host

    r = requests.post(
        f"{host}/api/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    if r.status_code != 200:
        raise SystemExit(f"No se pudo iniciar sesión con {email}: HTTP {r.status_code}")
    contexto["token"] = r.json()["token"]


@events.test_stop.add_listener
def terminar(environment, **_):
    """Revoca el token al finalizar la prueba."""
    if contexto["token"]:
        try:
            requests.post(
                f"{environment.host}/api/auth/logout",
                headers={"Authorization": f"Bearer {contexto['token']}"},
                timeout=10,
            )
        except Exception:
            pass
        contexto["token"] = None


class UsuarioReportesNotificaciones(HttpUser):
    wait_time = between(*PAUSA)

    def cabeceras(self):
        return {
            "Authorization": f"Bearer {contexto['token']}",
            "X-Correlation-Id": f"lt-{uuid.uuid4()}",
            "Accept": "application/json",
        }

    @tag("c1")
    @task
    def c1_dashboard(self):
        self.client.get(
            "/api/dashboard",
            headers=self.cabeceras(),
            name="C1 GET /api/dashboard",
        )

    @tag("c2")
    @task
    def c2_valorizacion_json(self):
        agrupar = random.choice(["producto", "categoria", "bodega"])
        self.client.get(
            f"/api/reportes/valorizacion?agrupar={agrupar}",
            headers=self.cabeceras(),
            name="C2 GET /api/reportes/valorizacion [JSON]",
        )

    @tag("c3")
    @task
    def c3_valorizacion_csv(self):
        cabeceras = self.cabeceras()
        cabeceras["Accept"] = "text/csv"
        self.client.get(
            "/api/reportes/valorizacion?formato=csv",
            headers=cabeceras,
            name="C3 GET /api/reportes/valorizacion?formato=csv [CSV]",
        )

    @tag("c4")
    @task
    def c4_rotacion(self):
        self.client.get(
            "/api/reportes/rotacion",
            headers=self.cabeceras(),
            name="C4 GET /api/reportes/rotacion",
        )

    @tag("c5")
    @task
    def c5_stock_bajo(self):
        self.client.get(
            "/api/reportes/stock-bajo",
            headers=self.cabeceras(),
            name="C5 GET /api/reportes/stock-bajo",
        )

    @tag("c6")
    @task
    def c6_registro_dispositivo(self):
        cuerpo = {
            "token_fcm": f"fcm_token_lt_{uuid.uuid4().hex[:16]}",
            "plataforma": random.choice(["android", "ios", "web"]),
        }
        with self.client.post(
            "/api/dispositivos",
            json=cuerpo,
            headers=self.cabeceras(),
            name="C6 POST /api/dispositivos",
            catch_response=True,
        ) as r:
            if r.status_code != 201:
                r.failure(f"HTTP {r.status_code}")

    @tag("c7")
    @task
    def c7_listar_notificaciones(self):
        self.client.get(
            "/api/notificaciones?per_page=20",
            headers=self.cabeceras(),
            name="C7 GET /api/notificaciones",
        )
