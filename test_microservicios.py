"""Ejecutor unificado de pruebas unitarias para todos los microservicios desarrollados.

Uso desde la raiz del repositorio:
    python test_microservicios.py
    npm test

Ejecuta las suites unitarias y de mocking de endpoints de:
1. MS-Productos (Flask / pytest)
2. MS-Inventario (Flask / pytest)
3. MS-Proveedores (Express / Jest + Supertest)
4. MS-Compras (Flask / pytest)
5. MS-Reportes (Flask / pytest)
6. MS-Notificaciones (Express / Jest + Supertest)
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

RAIZ = Path(__file__).resolve().parent


def _puerto_abierto(host: str, port: int, timeout: float = 0.15) -> bool:
    """Comprueba rapidamente si un puerto TCP local acepta conexiones."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _resolver_pytest(carpeta_servicio: Path) -> list[str]:
    """Busca el ejecutable de pytest en entornos virtuales del repositorio o en PATH."""
    candidatos = [
        carpeta_servicio / ".venv" / "Scripts" / "pytest.exe",
        carpeta_servicio / ".venv" / "bin" / "pytest",
        RAIZ / "MS-Compras" / ".venv" / "Scripts" / "pytest.exe",
        RAIZ / "MS-Compras" / ".venv" / "bin" / "pytest",
        RAIZ / ".venv" / "Scripts" / "pytest.exe",
        RAIZ / ".venv" / "bin" / "pytest",
    ]
    for ruta in candidatos:
        if ruta.exists():
            return [str(ruta)]

    en_path = shutil.which("pytest")
    if en_path:
        return [en_path]
    return [sys.executable, "-m", "pytest"]


def _resolver_npm() -> str:
    """Devuelve el ejecutable de npm compatible con Windows, Linux y macOS."""
    if os.name == "nt":
        return shutil.which("npm.cmd") or shutil.which("npm") or "npm.cmd"
    return shutil.which("npm") or "npm"


def _suites_microservicios() -> list[tuple[str, Path, list[str]]]:
    npm_cmd = _resolver_npm()

    # Si los contenedores MySQL de desarrollo (33061/33062) estan activos se incluye toda la
    # carpeta tests/; si no, se ejecutan directamente las suites unitarias y de mocking para
    # evitar esperas de timeout TCP en pruebas de integracion de BD.
    archivos_productos = (
        ["-v"]
        if _puerto_abierto("127.0.0.1", 33061)
        else [
            "-v",
            "tests/test_base.py",
            "tests/test_db.py",
            "tests/test_json.py",
            "tests/test_utilidades.py",
            "tests/test_endpoints_mock.py",
        ]
    )

    archivos_inventario = (
        ["-v"]
        if _puerto_abierto("127.0.0.1", 33062)
        else [
            "-v",
            "tests/test_base.py",
            "tests/test_cliente_productos.py",
            "tests/test_consumidor.py",
            "tests/test_db.py",
            "tests/test_eventos.py",
            "tests/test_json.py",
            "tests/test_motor_movimientos.py",
            "tests/test_reintento_db.py",
            "tests/test_utilidades.py",
            "tests/test_endpoints_mock.py",
        ]
    )

    archivos_reportes = (
        ["-v"]
        if _puerto_abierto("127.0.0.1", 33065)
        else [
            "-v",
            "tests/test_paso2_1.py",
            "tests/test_endpoints_mock.py",
        ]
    )

    return [
        (
            "MS-Productos (Flask)",
            RAIZ / "MS-Productos",
            [*_resolver_pytest(RAIZ / "MS-Productos"), *archivos_productos],
        ),
        (
            "MS-Inventario (Flask)",
            RAIZ / "MS-Inventario",
            [*_resolver_pytest(RAIZ / "MS-Inventario"), *archivos_inventario],
        ),
        (
            "MS-Proveedores (Express)",
            RAIZ / "MS-Proveedores",
            [npm_cmd, "test"],
        ),
        (
            "MS-Compras (Flask)",
            RAIZ / "MS-Compras",
            [*_resolver_pytest(RAIZ / "MS-Compras"), "-v"],
        ),
        (
            "MS-Reportes (Flask)",
            RAIZ / "MS-Reportes",
            [*_resolver_pytest(RAIZ / "MS-Reportes"), *archivos_reportes],
        ),
        (
            "MS-Notificaciones (Express)",
            RAIZ / "MS-Notificaciones",
            [npm_cmd, "test"],
        ),
    ]


def main() -> int:
    suites = _suites_microservicios()
    resultados: list[tuple[str, int, float]] = []

    print("=" * 78)
    print(" EJECUCION UNIFICADA DE PRUEBAS UNITARIAS DE MICROSERVICIOS")
    print("=" * 78)

    inicio_global = time.perf_counter()

    for nombre, directorio, comando in suites:
        print(f"\n>>> Ejecutando suite: {nombre}")
        print(f"    Directorio: {directorio.relative_to(RAIZ)}")
        t0 = time.perf_counter()
        proc = subprocess.run(comando, cwd=str(directorio), check=False)
        duracion = time.perf_counter() - t0
        resultados.append((nombre, proc.returncode, duracion))

    duracion_total = time.perf_counter() - inicio_global

    print("\n" + "=" * 78)
    print(" RESUMEN DE RESULTADOS POR MICROSERVICIO")
    print("=" * 78)
    fallos = 0
    for nombre, codigo, duracion in resultados:
        estado = "APROBADO (OK)" if codigo == 0 else f"FALLO (exit {codigo})"
        if codigo != 0:
            fallos += 1
        print(f" - {nombre:<28} | {estado:<18} | {duracion:6.2f}s")

    print("-" * 78)
    print(
        f" Total microservicios evaluados: {len(resultados)} | "
        f"Aprobados: {len(resultados) - fallos} | Fallidos: {fallos} | "
        f"Tiempo total: {duracion_total:.2f}s"
    )
    print("=" * 78)

    return 1 if fallos > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
