"""Pruebas de rendimiento del bloque C (Reportes y Notificaciones), a través del gateway.

C1 GET /api/dashboard                      C2 GET /api/reportes/valorizacion (JSON)
C3 GET /api/reportes/valorizacion?formato=csv (CSV)
C4 GET /api/reportes/rotacion              C5 GET /api/reportes/stock-bajo
C6 POST /api/dispositivos                  C7 GET /api/notificaciones

Cada prueba es una clase de usuario (C1Dashboard ... C7Notificaciones), para elegirla
en la interfaz web (con --class-picker), y conserva su etiqueta (--tags c1 ... c7),
que usa ejecutar.sh en las corridas sin interfaz. El token se obtiene de forma perezosa
una sola vez en on_start con el usuario de pruebas/locust/.env y lo comparten todos los
usuarios virtuales (el login del gateway admite 5 intentos por minuto).
"""

import os
import random
import threading
import uuid
from pathlib import Path

import requests
from locust import HttpUser, between, events, tag, task

AQUI = Path(__file__).resolve().parent
PAUSA = (float(os.getenv("LT_PAUSA_MIN", "1")), float(os.getenv("LT_PAUSA_MAX", "3")))
TOKENS_FCM = [f"fcm_token_lt_{n:04d}" for n in range(1, 101)]

contexto = {"token": None, "obtuvo_token": False, "dispositivos": {}}
lock_login = threading.Lock()
lock_dispositivos = threading.Lock()


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
    """Descarta las clases sin tareas cuando se usa --tags."""
    # Con --tags (ejecutar.sh), Locust filtra las tareas justo antes de este evento:
    # se quitan las clases que quedaron vacías, que fallarían al crearse.
    if environment.parsed_options and getattr(environment.parsed_options, "tags", None):
        environment.user_classes[:] = [clase for clase in environment.user_classes if clase.tasks]


@events.test_stop.add_listener
def terminar(environment, **_):
    """Revoca el token solo si este módulo lo obtuvo y limpia dispositivos registrados."""
    import time
    time.sleep(1)
    token = contexto.get("token")
    if token:
        cabeceras = {"Authorization": f"Bearer {token}"}
        while True:
            with lock_dispositivos:
                if not contexto["dispositivos"]:
                    break
                ids_borrar = list(set(contexto["dispositivos"].values()))
                contexto["dispositivos"].clear()
            for id_disp in ids_borrar:
                try:
                    requests.delete(
                        f"{environment.host}/api/dispositivos/{id_disp}",
                        headers=cabeceras,
                        timeout=5,
                    )
                except Exception:
                    pass

    if token and contexto.get("obtuvo_token"):
        try:
            requests.post(
                f"{environment.host}/api/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
        except Exception:
            pass
        contexto["token"] = None
        contexto["obtuvo_token"] = False


class UsuarioBloqueC(HttpUser):
    """Base común: pausa, login perezoso y cabeceras. No se ejecuta sola."""

    abstract = True
    wait_time = between(*PAUSA)

    def on_start(self):
        with lock_login:
            if not contexto["token"]:
                env = leer_env(AQUI / ".env")
                if not env.get("LT_EMAIL") or not env.get("LT_PASSWORD"):
                    raise SystemExit("Falta pruebas/locust/.env: ejecuta preparar_datos.py")
                host = self.environment.host
                r = requests.post(
                    f"{host}/api/auth/login",
                    json={"email": env["LT_EMAIL"], "password": env["LT_PASSWORD"]},
                    timeout=10,
                )
                if r.status_code != 200:
                    raise SystemExit(f"No se pudo iniciar sesión con el usuario de prueba: HTTP {r.status_code}")
                contexto["token"] = r.json()["token"]
                contexto["obtuvo_token"] = True

    def cabeceras(self):
        return {
            "Authorization": f"Bearer {contexto['token']}",
            "X-Correlation-Id": f"lt-{uuid.uuid4()}",
            "Accept": "application/json",
        }


class C1Dashboard(UsuarioBloqueC):
    """C1: métricas consolidadas del dashboard; gateway y ms-reportes."""

    @tag("c1")
    @task
    def dashboard(self):
        self.client.get(
            "/api/dashboard",
            headers=self.cabeceras(),
            name="C1 GET /api/dashboard",
        )


class C2ValorizacionJson(UsuarioBloqueC):
    """C2: valorización de inventario en formato JSON; gateway y ms-reportes."""

    @tag("c2")
    @task
    def valorizacion_json(self):
        agrupar = random.choice(["producto", "categoria", "bodega"])
        self.client.get(
            f"/api/reportes/valorizacion?agrupar={agrupar}",
            headers=self.cabeceras(),
            name="C2 GET /api/reportes/valorizacion [JSON]",
        )


class C3ValorizacionCsv(UsuarioBloqueC):
    """C3: exportación de valorización en formato CSV; gateway y ms-reportes."""

    @tag("c3")
    @task
    def valorizacion_csv(self):
        cabeceras = self.cabeceras()
        cabeceras["Accept"] = "text/csv"
        self.client.get(
            "/api/reportes/valorizacion?formato=csv",
            headers=cabeceras,
            name="C3 GET /api/reportes/valorizacion?formato=csv [CSV]",
        )


class C4Rotacion(UsuarioBloqueC):
    """C4: reporte de rotación de inventario; gateway y ms-reportes."""

    @tag("c4")
    @task
    def rotacion(self):
        self.client.get(
            "/api/reportes/rotacion",
            headers=self.cabeceras(),
            name="C4 GET /api/reportes/rotacion",
        )


class C5StockBajo(UsuarioBloqueC):
    """C5: reporte de productos con stock bajo umbral; gateway y ms-reportes."""

    @tag("c5")
    @task
    def stock_bajo(self):
        self.client.get(
            "/api/reportes/stock-bajo",
            headers=self.cabeceras(),
            name="C5 GET /api/reportes/stock-bajo",
        )


class C6Dispositivos(UsuarioBloqueC):
    """C6: registro y actualización de tokens FCM de dispositivos; gateway y ms-notificaciones."""

    @tag("c6")
    @task
    def registro_dispositivo(self):
        token_fcm = random.choice(TOKENS_FCM)
        cuerpo = {
            "token_fcm": token_fcm,
            "plataforma": random.choice(["android", "ios", "web"]),
        }
        with self.client.post(
            "/api/dispositivos",
            json=cuerpo,
            headers=self.cabeceras(),
            name="C6 POST /api/dispositivos",
            catch_response=True,
        ) as r:
            if r.status_code == 201:
                try:
                    datos = r.json()
                    id_disp = datos.get("id_dispositivo")
                    if id_disp:
                        with lock_dispositivos:
                            contexto["dispositivos"][token_fcm] = id_disp
                except Exception:
                    pass
            else:
                r.failure(f"HTTP {r.status_code}")


class C7Notificaciones(UsuarioBloqueC):
    """C7: consulta paginada del historial de notificaciones; gateway y ms-notificaciones."""

    @tag("c7")
    @task
    def listar_notificaciones(self):
        self.client.get(
            "/api/notificaciones?per_page=20",
            headers=self.cabeceras(),
            name="C7 GET /api/notificaciones",
        )
