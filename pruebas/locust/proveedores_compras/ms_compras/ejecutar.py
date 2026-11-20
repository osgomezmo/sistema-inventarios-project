"""Ejecutor multiplataforma (Windows/Linux/macOS) para las pruebas Locust P08-P15 de MS-Compras.

Ejemplos:
    python ejecutar.py --listar
    python ejecutar.py P08
    python ejecutar.py P08 --usuarios 10 --duracion 30s
    python ejecutar.py solo --duracion 1m
    python ejecutar.py P13 --web
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys


@dataclass(frozen=True)
class DefinicionPrueba:
    codigo: str
    archivo: str
    tipo: str
    modo: str
    usuarios: int | None
    spawn_rate: int | None
    duracion: str | None
    usa_shape: bool
    descripcion: str


PRUEBAS: dict[str, DefinicionPrueba] = {
    "P08": DefinicionPrueba(
        codigo="P08",
        archivo="p08_carga_ordenes.py",
        tipo="Carga",
        modo="solo",
        usuarios=20,
        spawn_rate=5,
        duracion="10m",
        usa_shape=False,
        descripcion="Consultas mixtas de ordenes de compra, filtros, detalle, recepciones y /health",
    ),
    "P09": DefinicionPrueba(
        codigo="P09",
        archivo="p09_carga_devoluciones.py",
        tipo="Carga",
        modo="solo",
        usuarios=25,
        spawn_rate=5,
        duracion="10m",
        usa_shape=False,
        descripcion="Devoluciones a proveedores, filtros temporales y comparacion de paginacion",
    ),
    "P10": DefinicionPrueba(
        codigo="P10",
        archivo="p10_carga_validacion.py",
        tipo="Carga",
        modo="solo",
        usuarios=30,
        spawn_rate=6,
        duracion="5m",
        usa_shape=False,
        descripcion="Validacion JSON, autenticacion 401, RBAC 403, 404 y conflictos 409",
    ),
    "P11": DefinicionPrueba(
        codigo="P11",
        archivo="p11_carga_mixta.py",
        tipo="Carga",
        modo="integrado",
        usuarios=20,
        spawn_rate=4,
        duracion="10m",
        usa_shape=False,
        descripcion="Mezcla 75% GET + 25% POST/PUT/aprobar/anular (requiere MS-Proveedores y RabbitMQ)",
    ),
    "P12": DefinicionPrueba(
        codigo="P12",
        archivo="p12_carga_ciclo_completo.py",
        tipo="Carga",
        modo="integrado",
        usuarios=15,
        spawn_rate=3,
        duracion="10m",
        usa_shape=False,
        descripcion="Ciclo completo crear -> aprobar -> recepcion parcial/total -> devolucion",
    ),
    "P13": DefinicionPrueba(
        codigo="P13",
        archivo="p13_estres_lecturas.py",
        tipo="Estres",
        modo="solo",
        usuarios=None,
        spawn_rate=None,
        duracion=None,
        usa_shape=True,
        descripcion="Rampa escalonada 20->200u (+20/30s) en lecturas para saturar pool MySQL/Gunicorn",
    ),
    "P14": DefinicionPrueba(
        codigo="P14",
        archivo="p14_estres_escrituras.py",
        tipo="Estres",
        modo="integrado",
        usuarios=None,
        spawn_rate=None,
        duracion=None,
        usa_shape=True,
        descripcion="Rampa escalonada 15->120u (+15/30s) en mezcla con escrituras y RabbitMQ",
    ),
    "P15": DefinicionPrueba(
        codigo="P15",
        archivo="p15_capacidad_soak.py",
        tipo="Capacidad (soak)",
        modo="solo",
        usuarios=40,
        spawn_rate=5,
        duracion="60m",
        usa_shape=False,
        descripcion="Carga sostenida prolongada para detectar deriva de latencia, memoria y pool",
    ),
}


def localizar_locust(carpeta_actual: Path) -> str:
    candidatos = [
        carpeta_actual.parent / ".venv" / "Scripts" / "locust.exe",
        carpeta_actual.parent / ".venv" / "bin" / "locust",
        carpeta_actual.parent.parent / ".venv" / "Scripts" / "locust.exe",
        carpeta_actual.parent.parent / ".venv" / "bin" / "locust",
    ]
    for ruta in candidatos:
        if ruta.exists():
            return str(ruta)
    en_path = shutil.which("locust")
    if en_path:
        return en_path
    raise SystemExit(
        "No se encontro el ejecutable 'locust'. Instale dependencias con: "
        "pip install -r ../requirements.txt"
    )


def imprimir_catalogo() -> None:
    print(f"{'ID':<5} {'Tipo':<17} {'Modo':<10} {'Perfil defecto':<22} Descripcion")
    print("-" * 105)
    for prueba in PRUEBAS.values():
        perfil = (
            "LoadTestShape"
            if prueba.usa_shape
            else f"{prueba.usuarios}u / {prueba.spawn_rate}/s / {prueba.duracion}"
        )
        print(
            f"{prueba.codigo:<5} {prueba.tipo:<17} {prueba.modo:<10} "
            f"{perfil:<22} {prueba.descripcion}"
        )


def ejecutar_prueba(
    prueba: DefinicionPrueba,
    carpeta: Path,
    locust_bin: str,
    host: str,
    salida_base: Path,
    web: bool,
    usuarios: int | None,
    spawn_rate: int | None,
    duracion: str | None,
) -> int:
    archivo = carpeta / prueba.archivo
    dir_salida = salida_base / prueba.codigo
    dir_salida.mkdir(parents=True, exist_ok=True)

    cmd = [locust_bin, "-f", str(archivo), "--host", host]
    if not web:
        cmd.extend(
            [
                "--headless",
                "--csv",
                str(dir_salida / prueba.codigo),
                "--html",
                str(dir_salida / f"{prueba.codigo}.html"),
                "--loglevel",
                os.getenv("LT_LOGLEVEL", "WARNING"),
            ]
        )
        if not prueba.usa_shape:
            u = usuarios or int(os.getenv("LT_USUARIOS", str(prueba.usuarios or 20)))
            r = spawn_rate or int(os.getenv("LT_SPAWN_RATE", str(prueba.spawn_rate or 5)))
            t = duracion or os.getenv("LT_DURACION", prueba.duracion or "5m")
            cmd.extend(["-u", str(u), "-r", str(r), "-t", t])

    print(
        f"[{prueba.codigo}] Tipo={prueba.tipo} | Modo={prueba.modo} | Host={host} | "
        f"Salida={dir_salida}"
    )
    resultado = subprocess.run(cmd, cwd=str(carpeta), check=False)
    return resultado.returncode


def main() -> int:
    carpeta = Path(__file__).resolve().parent
    salida_defecto = (
        Path(os.getenv("LT_SALIDA"))
        if os.getenv("LT_SALIDA")
        else carpeta.parent.parent.parent / "resultados" / "proveedores_compras"
    )
    host_defecto = os.getenv("HOST") or os.getenv("LT_HOST") or "http://127.0.0.1:5004"

    parser = argparse.ArgumentParser(
        description="Ejecutor de pruebas de rendimiento Locust para MS-Compras (P08-P15)."
    )
    parser.add_argument(
        "objetivo",
        nargs="?",
        help="Codigo P08..P15, 'solo' (P08,P09,P10,P13,P15), 'integrado' (P11,P12,P14) o 'todas'",
    )
    parser.add_argument("--listar", action="store_true", help="Muestra la tabla de pruebas P08-P15")
    parser.add_argument("--host", default=host_defecto, help=f"URL base (defecto {host_defecto})")
    parser.add_argument("--salida", type=Path, default=salida_defecto, help="Carpeta de resultados")
    parser.add_argument("--web", action="store_true", help="Abre interfaz web de Locust en lugar de headless")
    parser.add_argument("-u", "--usuarios", type=int, default=None, help="Sobrescribe usuarios (no aplica a LoadTestShape)")
    parser.add_argument("-r", "--spawn-rate", type=int, default=None, help="Sobrescribe spawn rate")
    parser.add_argument("-t", "--duracion", default=None, help="Sobrescribe duracion (ej. 30s, 5m)")
    args = parser.parse_args()

    if args.listar or not args.objetivo:
        imprimir_catalogo()
        return 0

    clave = args.objetivo.strip().upper()
    if clave == "SOLO":
        seleccion = [p for p in PRUEBAS.values() if p.modo == "solo"]
    elif clave == "INTEGRADO":
        seleccion = [p for p in PRUEBAS.values() if p.modo == "integrado"]
    elif clave == "TODAS":
        seleccion = list(PRUEBAS.values())
    elif clave in PRUEBAS:
        seleccion = [PRUEBAS[clave]]
    else:
        print(f"Objetivo desconocido: {args.objetivo}. Use P08..P15, solo, integrado o todas.", file=sys.stderr)
        return 2

    locust_bin = localizar_locust(carpeta)
    codigo_final = 0
    for prueba in seleccion:
        rc = ejecutar_prueba(
            prueba=prueba,
            carpeta=carpeta,
            locust_bin=locust_bin,
            host=args.host,
            salida_base=args.salida,
            web=args.web,
            usuarios=args.usuarios,
            spawn_rate=args.spawn_rate,
            duracion=args.duracion,
        )
        if rc != 0:
            codigo_final = rc
            print(f"[{prueba.codigo}] Finalizo con codigo {rc} (revisar CSV/HTML en {args.salida / prueba.codigo})")

    return codigo_final


if __name__ == "__main__":
    raise SystemExit(main())
