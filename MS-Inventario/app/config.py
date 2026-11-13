import os
from pathlib import Path

from dotenv import load_dotenv

RUTA_ENV = Path(__file__).resolve().parent.parent / ".env"


def cargar_configuracion():
    load_dotenv(RUTA_ENV)
    return {
        "SERVICE_TOKEN": os.getenv("SERVICE_TOKEN", "").strip(),
        "DB_HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "DB_PORT": int(os.getenv("DB_PORT", "33062")),
        "DB_USER": os.getenv("DB_USER", ""),
        "DB_PASSWORD": os.getenv("DB_PASSWORD", ""),
        "DB_NAME": os.getenv("DB_NAME", "ms_inventario"),
    }
