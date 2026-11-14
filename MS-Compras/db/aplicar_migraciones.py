"""Script idempotente para aplicar migraciones SQL de ms-compras."""

import os
from pathlib import Path

from dotenv import load_dotenv
import mysql.connector

DIRECTORIO_RAIZ = Path(__file__).resolve().parent.parent
DIRECTORIO_MIGRACIONES = Path(__file__).resolve().parent

load_dotenv(DIRECTORIO_RAIZ / ".env")


def _validar_identificador_sql(nombre: str) -> str:
    """Valida que el nombre de base de datos sea seguro para DDL."""
    if not nombre or not all(c.isalnum() or c == "_" for c in nombre):
        raise ValueError(f"Nombre de base de datos invalido: {nombre!r}")
    return nombre


def _dividir_sentencias_sql(contenido: str) -> list[str]:
    """Separa sentencias SQL ignorando comentarios de linea '--'."""
    lineas_limpias = [
        linea
        for linea in contenido.splitlines()
        if not linea.lstrip().startswith("--")
    ]
    bloque = "\n".join(lineas_limpias)
    return [stmt.strip() for stmt in bloque.split(";") if stmt.strip()]


def aplicar_migraciones() -> list[str]:
    """Aplica en orden los archivos .sql pendientes dentro de db/."""
    db_host = os.getenv("DB_HOST", "127.0.0.1")
    db_port = int(os.getenv("DB_PORT", "3306"))
    db_user = os.getenv("DB_USER", "compras_user")
    db_password = os.getenv("DB_PASSWORD", "changeme")
    db_name = _validar_identificador_sql(os.getenv("DB_NAME", "mscompras"))

    conexion = mysql.connector.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        time_zone="+00:00",
        charset="utf8mb4",
        collation="utf8mb4_0900_ai_ci",
        autocommit=False,
    )

    aplicadas: list[str] = []
    try:
        cursor = conexion.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
        )
        cursor.execute(f"USE `{db_name}`")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) NOT NULL,
                aplicada_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
                PRIMARY KEY (version)
            ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
            """
        )
        conexion.commit()

        cursor.execute("SELECT version FROM schema_migrations")
        existentes = {fila[0] for fila in cursor.fetchall()}

        archivos_sql = sorted(DIRECTORIO_MIGRACIONES.glob("*.sql"))
        for archivo in archivos_sql:
            if archivo.name in existentes:
                continue

            contenido = archivo.read_text(encoding="utf-8")
            for sentencia in _dividir_sentencias_sql(contenido):
                cursor.execute(sentencia)

            cursor.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (archivo.name,),
            )
            conexion.commit()
            aplicadas.append(archivo.name)

        cursor.close()
    finally:
        conexion.close()

    return aplicadas


if __name__ == "__main__":
    resultado = aplicar_migraciones()
    if resultado:
        print(f"[ms-compras] Migraciones aplicadas: {', '.join(resultado)}")
    else:
        print("[ms-compras] Esquema al dia. No hay migraciones pendientes.")
