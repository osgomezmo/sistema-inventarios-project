"""Abre la interfaz web de Locust para correr las pruebas de los bloques B y C.

Uso (desde pruebas/locust/, con el venv activado; Windows, Mac o Linux):

    python interfaz.py            # escenarios normal y pico (pausa de 1 a 3 s)
    python interfaz.py --estres   # agrega la forma de estrés (20 a 200 usuarios)

Pasos:
1. Comprueba que el gateway responde en LT_HOST (por defecto http://127.0.0.1:8000).
2. Lee el administrador de LT_ADMIN_EMAIL y LT_ADMIN_PASSWORD o, si no están, de
   ADMIN_EMAIL y ADMIN_PASSWORD en gateway/.env.
3. Si falta el usuario de prueba o los datos LT, los crea con preparar_datos.py.
4. Lanza Locust en el puerto 8089 de LT_WEB_HOST (por defecto 127.0.0.1; en el
   contenedor, 0.0.0.0) con el selector de clases: en la página se
   elige la prueba (B1AuthMe ... B6Kardex o C1Dashboard ... C7Notificaciones), los usuarios y la tasa.

Nunca imprime contraseñas ni tokens.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
HOST = os.getenv("LT_HOST", "http://127.0.0.1:8000").rstrip("/")
# Dirección de la interfaz web: 127.0.0.1 en la máquina local, 0.0.0.0 en el contenedor
HOST_WEB = os.getenv("LT_WEB_HOST", "127.0.0.1").strip() or "127.0.0.1"
PUERTO_WEB = "8089"


def leer_env(ruta):
    """Lee un .env simple (CLAVE=valor) sin imprimir nada."""
    valores = {}
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                clave, valor = linea.split("=", 1)
                valores[clave.strip()] = valor.strip().strip('"').strip("'")
    return valores


def pedir(metodo, ruta, cuerpo=None, token=None):
    """Petición al gateway; devuelve (código, JSON o None). 0 si no hay respuesta."""
    cabeceras = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(HOST + ruta, data=datos, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=10) as respuesta:
            texto = respuesta.read()
            return respuesta.status, (json.loads(texto) if texto else None)
    except urllib.error.HTTPError as error:
        return error.code, None
    except (urllib.error.URLError, OSError):
        return 0, None


def comprobar_gateway():
    # En el contenedor el gateway puede tardar en arrancar: se reintenta hasta
    # LT_ESPERA_GATEWAY segundos (por defecto 0: se avisa de inmediato)
    limite = time.monotonic() + float(os.getenv("LT_ESPERA_GATEWAY", "0") or 0)
    codigo, _ = pedir("GET", "/up")
    while codigo != 200 and time.monotonic() < limite:
        time.sleep(3)
        codigo, _ = pedir("GET", "/up")
    if codigo != 200:
        sys.exit(
            f"El gateway no responde en {HOST} (código {codigo or 'sin respuesta'}).\n"
            "Levanta los servicios con 'docker compose up -d' (RabbitMQ, ms-productos, "
            "ms-inventario y gateway) o indica otra dirección con la variable LT_HOST."
        )
    print(f"Gateway: responde en {HOST}")


def credenciales_admin():
    email = os.getenv("LT_ADMIN_EMAIL", "").strip()
    password = os.getenv("LT_ADMIN_PASSWORD", "").strip()
    if not (email and password):
        env = leer_env(RAIZ / "gateway" / ".env")
        email, password = env.get("ADMIN_EMAIL", ""), env.get("ADMIN_PASSWORD", "")
    if not (email and password):
        sys.exit(
            "Faltan las credenciales del administrador del gateway.\n"
            "Defínelas en las variables LT_ADMIN_EMAIL y LT_ADMIN_PASSWORD, o como "
            "ADMIN_EMAIL y ADMIN_PASSWORD en gateway/.env."
        )
    return email, password


def datos_listos():
    """True si el usuario de prueba entra y existen las bodegas y productos LT."""
    env = leer_env(AQUI / ".env")
    if not (env.get("LT_EMAIL") and env.get("LT_PASSWORD")):
        return False
    codigo, cuerpo = pedir("POST", "/api/auth/login", {"email": env["LT_EMAIL"], "password": env["LT_PASSWORD"]})
    if codigo != 200:
        return False
    token = cuerpo["token"]
    try:
        _, bodegas = pedir("GET", "/api/bodegas?per_page=100", token=token)
        codigos = {b["codigo"] for b in (bodegas or {}).get("data", [])}
        _, productos = pedir("GET", "/api/productos?skus=LT-0001,LT-2000", token=token)
        total = (productos or {}).get("meta", {}).get("total", 0)
        return {"LT-B1", "LT-B2"} <= codigos and total == 2
    finally:
        pedir("POST", "/api/auth/logout", {}, token=token)


def preparar(email, password):
    """Crea los datos LT con las funciones de preparar_datos.py."""
    print("Faltan el usuario de prueba o los datos LT: se crean (tarda unos 3 minutos)...")
    os.environ["LT_HOST"] = HOST
    sys.path.insert(0, str(AQUI))
    import preparar_datos as prep

    admin = prep.Gateway(email, password)
    prep.asegurar_usuario(admin)
    categorias = prep.asegurar_categorias(admin)
    prep.asegurar_productos(admin, categorias)
    bodegas = prep.asegurar_bodegas(admin)
    prep.asegurar_saldos(admin, bodegas)
    admin.pedir("POST", "/auth/logout", esperado=(200, 204))
    print("Datos LT listos.")


def lanzar_locust(estres):
    archivos = str(AQUI / "bloque_b.py") + "," + str(AQUI / "bloque_c.py")
    entorno = dict(os.environ)
    if estres:
        archivos += "," + str(AQUI / "forma_estres.py")
        entorno.update(LT_PAUSA_MIN="0.5", LT_PAUSA_MAX="1.5")
    else:
        entorno.update(LT_PAUSA_MIN="1", LT_PAUSA_MAX="3")
    comando = [sys.executable, "-m", "locust", "-f", archivos, "--class-picker", "--host", HOST,
               "--web-host", HOST_WEB, "--web-port", PUERTO_WEB]
    print(f"\nAbre http://127.0.0.1:{PUERTO_WEB} en el navegador y elige una prueba (B1AuthMe ... B6Kardex, C1Dashboard ... C7Notificaciones).")
    if estres:
        print("Modo estrés: elige también la forma FormaEstres en el selector.")
    print("Para terminar, presiona Ctrl+C en esta ventana.\n")
    proceso = subprocess.Popen(comando, cwd=AQUI, env=entorno)

    def detener(*_):
        proceso.terminate()  # docker stop: Locust termina ordenadamente

    signal.signal(signal.SIGTERM, detener)
    try:
        return proceso.wait()
    except KeyboardInterrupt:
        proceso.wait()
        return 0


def main():
    parser = argparse.ArgumentParser(description="Interfaz web de Locust para los bloques B y C.")
    parser.add_argument("--estres", action="store_true",
                        help="agrega la forma de estrés (de 20 a 200 usuarios, sumando 20 cada 30 s)")
    args = parser.parse_args()

    comprobar_gateway()
    if datos_listos():
        print("Usuario de prueba y datos LT: listos")
    else:
        # El administrador solo hace falta para crear los datos
        preparar(*credenciales_admin())
    sys.exit(lanzar_locust(args.estres))


if __name__ == "__main__":
    main()
