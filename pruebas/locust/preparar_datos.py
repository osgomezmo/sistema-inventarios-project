"""Carga los datos de las pruebas de rendimiento del bloque B a través del gateway.

Uso: .venv/bin/python preparar_datos.py  (desde pruebas/locust/)

Inicia sesión con el administrador del gateway (LT_ADMIN_EMAIL y LT_ADMIN_PASSWORD
o, si no están, ADMIN_EMAIL y ADMIN_PASSWORD de gateway/.env) en LT_HOST (por
defecto http://127.0.0.1:8000) y crea, si no existen: el usuario lt.jefe@ejemplo.invalid (jefe_bodega, con su
contraseña en pruebas/locust/.env), 20 categorías "LT Cat NN", 2000 productos
LT-0001 a LT-2000, las bodegas LT-B1, LT-B2 y LT-B3 y los saldos iniciales.
Es idempotente: reutiliza lo que ya existe y solo completa los saldos que falten.
Nunca imprime contraseñas ni tokens.
"""

import os
import secrets
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
HOST = os.getenv("LT_HOST", "http://127.0.0.1:8000")
ENV_PRUEBAS = AQUI / ".env"

EMAIL_JEFE = "lt.jefe@ejemplo.invalid"
CATEGORIAS = [f"LT Cat {n:02d}" for n in range(1, 21)]
SKUS = [f"LT-{n:04d}" for n in range(1, 2001)]
BODEGAS = {"LT-B1": "Bodega LT 1", "LT-B2": "Bodega LT 2", "LT-B3": "Bodega LT 3"}
SKUS_GRANDES = SKUS[:50]  # para salidas y traslados
# Tipos para los nombres: dan coincidencias a las búsquedas de B2
TIPOS = ["Leche", "Arroz", "Jabón", "Gaseosa", "Pan", "Aceite", "Queso", "Detergente", "Jugo", "Café"]
CANTIDAD_GRANDE = 1_000_000
CANTIDAD_PEQUENA = 20
COSTO = 100
HILOS = int(os.getenv("LT_HILOS", "3"))


def leer_env(ruta):
    """Lee un .env simple (CLAVE=valor) sin imprimir nada."""
    valores = {}
    if ruta.exists():
        for linea in ruta.read_text().splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                clave, valor = linea.split("=", 1)
                valores[clave.strip()] = valor.strip().strip('"').strip("'")
    return valores


class Gateway:
    def __init__(self, email, password):
        self.sesion = requests.Session()
        r = self.sesion.post(f"{HOST}/api/auth/login", json={"email": email, "password": password}, timeout=10)
        if r.status_code != 200:
            sys.exit(f"No se pudo iniciar sesión como {email}: HTTP {r.status_code}")
        self.sesion.headers["Authorization"] = f"Bearer {r.json()['token']}"

    def pedir(self, metodo, ruta, esperado=(200,), **kwargs):
        kwargs.setdefault("timeout", 30)
        cabeceras = {"X-Correlation-Id": f"lt-prep-{uuid.uuid4()}"}
        r = self.sesion.request(metodo, f"{HOST}/api{ruta}", headers=cabeceras, **kwargs)
        if r.status_code not in esperado:
            codigo = r.json().get("error", {}).get("codigo") if r.headers.get("content-type", "").startswith("application/json") else None
            raise RuntimeError(f"{metodo} {ruta}: HTTP {r.status_code} {codigo or ''}".strip())
        return r.json() if r.content else None

    def todos(self, ruta, **params):
        """Recorre un listado paginado {data, meta}."""
        pagina, filas = 1, []
        while True:
            cuerpo = self.pedir("GET", ruta, params={**params, "page": pagina, "per_page": 100})
            filas.extend(cuerpo["data"])
            if pagina * 100 >= cuerpo["meta"]["total"]:
                return filas
            pagina += 1


def asegurar_usuario(admin):
    env = leer_env(ENV_PRUEBAS)
    existentes = [u for u in admin.todos("/usuarios") if u["email"] == EMAIL_JEFE]
    if existentes:
        if not env.get("LT_PASSWORD"):
            sys.exit(f"{EMAIL_JEFE} ya existe pero falta su contraseña en pruebas/locust/.env; "
                     "ejecuta limpiar_datos.py y vuelve a preparar.")
        print(f"usuario {EMAIL_JEFE}: ya existe")
        return
    id_rol = next(r["id_rol"] for r in admin.pedir("GET", "/roles") if r["codigo"] == "jefe_bodega")
    password = secrets.token_urlsafe(24)
    # Primero el archivo (solo legible por el dueño) y después el usuario
    ENV_PRUEBAS.write_text(f"LT_EMAIL={EMAIL_JEFE}\nLT_PASSWORD={password}\n")
    ENV_PRUEBAS.chmod(0o600)
    admin.pedir("POST", "/usuarios", esperado=(201,), json={
        "nombre": "LT Jefe de bodega", "email": EMAIL_JEFE, "password": password, "id_rol": id_rol})
    print(f"usuario {EMAIL_JEFE}: creado (contraseña en pruebas/locust/.env)")


def asegurar_categorias(admin):
    ids = {c["nombre"]: c["id_categoria"] for c in admin.todos("/categorias") if c["nombre"] in CATEGORIAS}
    nuevas = 0
    for nombre in CATEGORIAS:
        if nombre not in ids:
            ids[nombre] = admin.pedir("POST", "/categorias", esperado=(201,), json={"nombre": nombre})["id_categoria"]
            nuevas += 1
    print(f"categorías: {len(ids)} ({nuevas} nuevas)")
    return [ids[n] for n in CATEGORIAS]


def asegurar_productos(admin, categorias):
    existentes = set()
    for i in range(0, len(SKUS), 100):
        lote = ",".join(SKUS[i:i + 100])
        existentes.update(p["sku"] for p in admin.pedir("GET", "/productos", params={"skus": lote, "per_page": 100})["data"])
    faltan = [(n, sku) for n, sku in enumerate(SKUS) if sku not in existentes]

    def crear(par):
        n, sku = par
        admin.pedir("POST", "/productos", esperado=(201,), json={
            "sku": sku, "nombre": f"{TIPOS[n % len(TIPOS)]} LT {n + 1:04d}", "marca": "LT",
            "id_categoria": categorias[n % len(categorias)], "unidad_medida": "UNIDAD",
            "precio_venta": 1000, "stock_minimo": 10})

    with ThreadPoolExecutor(HILOS) as hilos:
        list(hilos.map(crear, faltan))
    print(f"productos: {len(SKUS)} ({len(faltan)} nuevos)")


def asegurar_bodegas(admin):
    ids = {b["codigo"]: b["id_bodega"] for b in admin.todos("/bodegas") if b["codigo"] in BODEGAS}
    nuevas = 0
    for codigo, nombre in BODEGAS.items():
        if codigo not in ids:
            ids[codigo] = admin.pedir("POST", "/bodegas", esperado=(201,), json={
                "codigo": codigo, "nombre": nombre, "direccion": "Dirección de prueba"})["id_bodega"]
            nuevas += 1
    print(f"bodegas: {len(ids)} ({nuevas} nuevas)")
    return ids


def asegurar_saldos(admin, bodegas):
    objetivos = {}
    for sku in SKUS_GRANDES:
        objetivos[(sku, bodegas["LT-B1"])] = CANTIDAD_GRANDE
        objetivos[(sku, bodegas["LT-B2"])] = CANTIDAD_GRANDE
    for sku in SKUS[50:]:
        objetivos[(sku, bodegas["LT-B1"])] = CANTIDAD_PEQUENA

    actuales = {}
    for codigo in ("LT-B1", "LT-B2"):
        for fila in admin.todos("/stock", id_bodega=bodegas[codigo]):
            actuales[(fila["sku"], fila["id_bodega"])] = fila["cantidad"]
    # Solo se completa lo que falta para llegar a la cantidad objetivo
    ajustes = [(sku, id_bodega, objetivo - actuales.get((sku, id_bodega), 0))
               for (sku, id_bodega), objetivo in objetivos.items()
               if actuales.get((sku, id_bodega), 0) < objetivo]

    def ajustar(ajuste):
        sku, id_bodega, cantidad = ajuste
        admin.pedir("POST", "/movimientos", esperado=(201,), json={
            "sku": sku, "id_bodega": id_bodega, "tipo": "AJUSTE_POSITIVO", "cantidad": int(cantidad),
            "costo_unitario": COSTO, "motivo": "Saldo inicial de pruebas LT"})

    with ThreadPoolExecutor(HILOS) as hilos:
        list(hilos.map(ajustar, ajustes))
    print(f"saldos: {len(objetivos)} ({len(ajustes)} ajustes positivos)")


def credenciales_admin():
    """Administrador de LT_ADMIN_EMAIL/LT_ADMIN_PASSWORD o, si no están, de gateway/.env."""
    email = os.getenv("LT_ADMIN_EMAIL", "").strip()
    password = os.getenv("LT_ADMIN_PASSWORD", "").strip()
    if not (email and password):
        gateway_env = leer_env(RAIZ / "gateway" / ".env")
        email, password = gateway_env.get("ADMIN_EMAIL", ""), gateway_env.get("ADMIN_PASSWORD", "")
    if not (email and password):
        sys.exit("Faltan las credenciales del administrador: LT_ADMIN_EMAIL y LT_ADMIN_PASSWORD, "
                 "o ADMIN_EMAIL y ADMIN_PASSWORD en gateway/.env.")
    return email, password


def main():
    admin = Gateway(*credenciales_admin())
    asegurar_usuario(admin)
    categorias = asegurar_categorias(admin)
    asegurar_productos(admin, categorias)
    bodegas = asegurar_bodegas(admin)
    asegurar_saldos(admin, bodegas)
    admin.pedir("POST", "/auth/logout", esperado=(200, 204))  # no deja tokens del administrador
    print("listo")


if __name__ == "__main__":
    main()
