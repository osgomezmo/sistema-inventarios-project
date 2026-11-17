"""Aplica en orden los scripts SQL de db/ que aún no estén registrados.

Uso, desde la carpeta del servicio:

    python -m db.aplicar_migraciones

Cada script aplicado se registra en la tabla migraciones_aplicadas, así que
correrlo varias veces no repite nada. En MySQL las sentencias DDL (CREATE,
ALTER) confirman la transacción de forma implícita: si un script falla a mitad
de camino, no queda registrado y sus sentencias deben poder repetirse (por eso
se usa CREATE TABLE IF NOT EXISTS).
"""

import sys
from pathlib import Path

from app.config import cargar_configuracion
from app.db import transaccion
from app.errors import ApiError

CARPETA = Path(__file__).resolve().parent

CREAR_REGISTRO = """
CREATE TABLE IF NOT EXISTS migraciones_aplicadas (
    nombre VARCHAR(100) NOT NULL,
    aplicada_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (nombre)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
"""


def sentencias(texto):
    """Separa un script en sentencias, quitando las líneas de comentario."""
    lineas = [linea for linea in texto.splitlines() if not linea.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lineas).split(";") if s.strip()]


def scripts_pendientes(aplicadas):
    return [ruta for ruta in sorted(CARPETA.glob("*.sql")) if ruta.name not in aplicadas]


def aplicar(config=None):
    """Aplica los scripts pendientes y devuelve la lista de nombres aplicados."""
    config = config if config is not None else cargar_configuracion()

    with transaccion(config) as cursor:
        cursor.execute(CREAR_REGISTRO)
        cursor.execute("SELECT nombre FROM migraciones_aplicadas")
        aplicadas = {fila["nombre"] for fila in cursor.fetchall()}

    nuevas = []
    for ruta in scripts_pendientes(aplicadas):
        with transaccion(config) as cursor:
            for sentencia in sentencias(ruta.read_text(encoding="utf-8")):
                cursor.execute(sentencia)
            cursor.execute(
                "INSERT INTO migraciones_aplicadas (nombre) VALUES (%s)", (ruta.name,)
            )
        nuevas.append(ruta.name)
    return nuevas


def main():
    try:
        nuevas = aplicar()
    except ApiError as error:
        print(f"No se aplicaron los scripts: {error.mensaje}", file=sys.stderr)
        return 1

    if nuevas:
        for nombre in nuevas:
            print(f"Aplicado: {nombre}")
    else:
        print("No hay scripts pendientes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
