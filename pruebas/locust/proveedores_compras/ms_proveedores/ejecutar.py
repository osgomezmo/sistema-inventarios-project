#!/usr/bin/env python3
"""Ejecutor multiplataforma (Windows/Linux/macOS) de la suite Locust de MS-Proveedores (P01..P07).

Ejemplos:
  python ejecutar.py P01
  python ejecutar.py P05 --humo
  python ejecutar.py P07 --duracion 60m
  python ejecutar.py P02 --ui
  python ejecutar.py TODAS --humo
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ_SUITE = AQUI.parent
RAIZ_PRUEBAS = AQUI.parents[2]

PERFILES: dict[str, dict[str, object]] = {
    "P01": {
        "archivo": "p01_carga_lectura.py",
        "tipo": "carga",
        "usuarios": 25,
        "spawn": 5,
        "duracion": "5m",
        "descripcion": "Carga nominal de lectura del catalogo de proveedores",
    },
    "P02": {
        "archivo": "p02_carga_mixta.py",
        "tipo": "carga",
        "usuarios": 30,
        "spawn": 5,
        "duracion": "5m",
        "descripcion": "Carga mixta 80/20 (GET predominante + POST/PUT)",
    },
    "P03": {
        "archivo": "p03_carga_ciclo_vida.py",
        "tipo": "carga",
        "usuarios": 20,
        "spawn": 4,
        "duracion": "5m",
        "descripcion": "Carga de ciclo de vida completo de proveedor y contactos",
    },
    "P04": {
        "archivo": "p04_carga_productos.py",
        "tipo": "carga",
        "usuarios": 25,
        "spawn": 5,
        "duracion": "5m",
        "descripcion": "Carga transaccional de productos suministrados (UPSERT/consulta/baja)",
    },
    "P05": {
        "archivo": "p05_estres_lectura.py",
        "tipo": "estres",
        "descripcion": "Estres progresivo en lecturas y busquedas LIKE/EXISTS (20->200u)",
    },
    "P06": {
        "archivo": "p06_estres_escritura.py",
        "tipo": "estres",
        "descripcion": "Estres progresivo en escrituras transaccionales concurrentes (15->150u)",
    },
    "P07": {
        "archivo": "p07_capacidad_soak.py",
        "tipo": "capacidad",
        "usuarios": 40,
        "spawn": 5,
        "duracion": "15m",
        "descripcion": "Capacidad (soak) sostenida de operacion mixta (configurable a 60m)",
    },
}


def localizar_locust() -> list[str]:
    """Localiza el binario locust en entornos virtuales del proyecto o en PATH."""
    explicito = os.getenv("LOCUST_BIN")
    if explicito:
        return [explicito]

    candidatos = [
        RAIZ_SUITE / ".venv" / "Scripts" / "locust.exe",
        RAIZ_SUITE / ".venv" / "bin" / "locust",
        AQUI.parents[1] / ".venv" / "Scripts" / "locust.exe",
        AQUI.parents[1] / ".venv" / "bin" / "locust",
    ]
    for ruta in candidatos:
        if ruta.exists():
            return [str(ruta)]

    en_path = shutil.which("locust")
    if en_path:
        return [en_path]

    return [sys.executable, "-m", "locust"]


def ejecutar_escenario(
    prueba_id: str,
    host: str,
    salida_base: Path,
    modo_ui: bool,
    modo_humo: bool,
    usuarios_override: int | None,
    spawn_override: int | None,
    duracion_override: str | None,
) -> int:
    perfil = PERFILES[prueba_id]
    archivo = AQUI / str(perfil["archivo"])
    tipo = str(perfil["tipo"])

    env = os.environ.copy()
    env["HOST"] = host
    env["LT_HOST"] = host
    token = env.get("LT_SERVICE_TOKEN") or env.get("SERVICE_TOKEN") or "token-servicio-inventarios-2026-vm"
    env["SERVICE_TOKEN"] = token
    env["LT_SERVICE_TOKEN"] = token

    cmd = localizar_locust()

    if modo_ui:
        cmd.extend(["-f", str(archivo), "--host", host])
        print(f"[{prueba_id}] Abriendo Web UI de Locust contra {host} ({archivo.name})")
        return subprocess.call(cmd, env=env)

    dir_salida = salida_base / prueba_id
    dir_salida.mkdir(parents=True, exist_ok=True)

    cmd.extend(
        [
            "-f",
            str(archivo),
            "--headless",
            "--host",
            host,
            "--csv",
            str(dir_salida / prueba_id),
            "--html",
            str(dir_salida / f"{prueba_id}.html"),
            "--loglevel",
            "INFO",
        ]
    )

    if tipo == "estres":
        if modo_humo:
            env.setdefault("LT_PASO_USUARIOS", "5")
            env.setdefault("LT_PASO_SEGUNDOS", "10")
            env.setdefault("LT_MAX_USUARIOS", "15")
    else:
        if modo_humo:
            usuarios = usuarios_override or int(env.get("LT_USUARIOS", "5"))
            spawn = spawn_override or int(env.get("LT_SPAWN_RATE", "5"))
            duracion = duracion_override or env.get("LT_DURACION", "20s")
        else:
            usuarios = usuarios_override or int(env.get("LT_USUARIOS", str(perfil["usuarios"])))
            spawn = spawn_override or int(env.get("LT_SPAWN_RATE", str(perfil["spawn"])))
            duracion = duracion_override or env.get("LT_DURACION", str(perfil["duracion"]))
        cmd.extend(["-u", str(usuarios), "-r", str(spawn), "-t", str(duracion)])

    print(f"[{prueba_id}] {perfil['descripcion']} | Host: {host} | Reportes: {dir_salida}")
    return subprocess.call(cmd, env=env)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ejecutor de pruebas de rendimiento Locust para MS-Proveedores (P01..P07)."
    )
    parser.add_argument(
        "prueba",
        help="Identificador de la prueba (P01..P07) o TODAS.",
    )
    parser.add_argument("--host", default=os.getenv("LT_HOST") or os.getenv("HOST") or "http://127.0.0.1:5003")
    parser.add_argument("--ui", action="store_true", help="Ejecutar con interfaz web de Locust.")
    parser.add_argument("--humo", action="store_true", help="Ejecutar corrida corta de verificacion.")
    parser.add_argument("-u", "--usuarios", type=int, default=None, help="Sobrescribe numero de usuarios.")
    parser.add_argument("-r", "--spawn-rate", type=int, default=None, help="Sobrescribe spawn rate (u/s).")
    parser.add_argument("-t", "--duracion", default=None, help="Sobrescribe duracion (ej. 5m, 60m).")
    parser.add_argument(
        "--salida",
        default=os.getenv("LT_SALIDA", str(RAIZ_PRUEBAS / "resultados" / "proveedores_compras")),
        help="Directorio base donde guardar reportes CSV y HTML.",
    )
    args = parser.parse_args()

    objetivo = args.prueba.strip().upper()
    if objetivo == "TODAS":
        lista = list(PERFILES.keys())
    elif objetivo in PERFILES:
        lista = [objetivo]
    else:
        parser.error(f"Prueba no reconocida: {args.prueba}. Usa P01..P07 o TODAS.")
        return 2

    salida_base = Path(args.salida)
    codigo_final = 0
    for pid in lista:
        rc = ejecutar_escenario(
            prueba_id=pid,
            host=args.host,
            salida_base=salida_base,
            modo_ui=args.ui,
            modo_humo=args.humo,
            usuarios_override=args.usuarios,
            spawn_override=args.spawn_rate,
            duracion_override=args.duracion,
        )
        if rc != 0:
            codigo_final = rc
    return codigo_final


if __name__ == "__main__":
    raise SystemExit(main())
