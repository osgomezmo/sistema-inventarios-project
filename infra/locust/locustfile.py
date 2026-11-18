"""Pruebas de carga y rendimiento con Locust para MS-Notificaciones y MS-Reportes.

Endpoints evaluados a través del API Gateway:
- GET  /api/dashboard
- GET  /api/reportes/valorizacion
- GET  /api/reportes/valorizacion?formato=csv
- GET  /api/reportes/rotacion
- GET  /api/reportes/stock-bajo
- POST /api/dispositivos
- GET  /api/notificaciones
"""

import os
import random
import uuid
import requests
from locust import HttpUser, between, events, tag, task

contexto = {"token": None}


@events.test_start.add_listener
def on_test_start(environment, **_):
    """Autentica contra el API Gateway para obtener el token Sanctum."""
    host = environment.host
    service_token = os.getenv("SERVICE_TOKEN")
    if service_token:
        # Modo token directo
        contexto["token"] = service_token
        return

    email = os.getenv("ADMIN_EMAIL", "admin@inventario.local")
    password = os.getenv("ADMIN_PASSWORD", "Inventario2026")
    try:
        r = requests.post(
            f"{host}/api/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        if r.status_code == 200:
            contexto["token"] = r.json()["token"]
        else:
            # Fallback a token de servicio predeterminado
            contexto["token"] = "token-secreto-gateway-2026"
    except Exception:
        contexto["token"] = "token-secreto-gateway-2026"


@events.test_stop.add_listener
def on_test_stop(environment, **_):
    """Cierra sesión revocando el token."""
    if contexto["token"] and not os.getenv("SERVICE_TOKEN"):
        try:
            requests.post(
                f"{environment.host}/api/auth/logout",
                headers={"Authorization": f"Bearer {contexto['token']}"},
                timeout=5,
            )
        except Exception:
            pass


class UsuarioCarga(HttpUser):
    wait_time = between(1, 3)

    def cabeceras(self, accept="application/json"):
        token = contexto.get("token") or "token-secreto-gateway-2026"
        return {
            "Authorization": f"Bearer {token}",
            "X-Correlation-Id": f"locust-{uuid.uuid4()}",
            "Accept": accept,
        }

    @tag("dashboard")
    @task(3)
    def consultar_dashboard(self):
        self.client.get(
            "/api/dashboard",
            headers=self.cabeceras(),
            name="GET /api/dashboard",
        )

    @tag("valorizacion")
    @task(2)
    def reporte_valorizacion(self):
        agrupar = random.choice(["producto", "categoria", "bodega"])
        self.client.get(
            f"/api/reportes/valorizacion?agrupar={agrupar}",
            headers=self.cabeceras(),
            name="GET /api/reportes/valorizacion [JSON]",
        )

    @tag("valorizacion_csv")
    @task(1)
    def reporte_valorizacion_csv(self):
        self.client.get(
            "/api/reportes/valorizacion?formato=csv",
            headers=self.cabeceras(accept="text/csv"),
            name="GET /api/reportes/valorizacion [CSV]",
        )

    @tag("rotacion")
    @task(2)
    def reporte_rotacion(self):
        self.client.get(
            "/api/reportes/rotacion",
            headers=self.cabeceras(),
            name="GET /api/reportes/rotacion",
        )

    @tag("stock_bajo")
    @task(2)
    def reporte_stock_bajo(self):
        self.client.get(
            "/api/reportes/stock-bajo",
            headers=self.cabeceras(),
            name="GET /api/reportes/stock-bajo",
        )

    @tag("dispositivos")
    @task(1)
    def registrar_dispositivo(self):
        payload = {
            "token_fcm": f"fcm_test_{uuid.uuid4().hex[:16]}",
            "plataforma": random.choice(["android", "ios", "web"]),
        }
        with self.client.post(
            "/api/dispositivos",
            json=payload,
            headers=self.cabeceras(),
            name="POST /api/dispositivos",
            catch_response=True,
        ) as response:
            if response.status_code != 201:
                response.failure(f"HTTP {response.status_code}")

    @tag("notificaciones")
    @task(3)
    def listar_notificaciones(self):
        self.client.get(
            "/api/notificaciones?per_page=20",
            headers=self.cabeceras(),
            name="GET /api/notificaciones",
        )
