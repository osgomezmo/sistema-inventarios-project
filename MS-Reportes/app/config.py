import os
from pathlib import Path

from dotenv import load_dotenv

RUTA_ENV = Path(__file__).resolve().parent.parent / ".env"


def cargar_configuracion():
    load_dotenv(RUTA_ENV)
    return {
        "PORT": int(os.getenv("PORT", "5005")),
        "SERVICE_TOKEN": os.getenv("SERVICE_TOKEN", "").strip(),
        "DB_HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "DB_PORT": int(os.getenv("DB_PORT", "33065")),
        "DB_USER": os.getenv("DB_USER", "ms_reportes"),
        "DB_PASSWORD": os.getenv("DB_PASSWORD", "reportes_secret_2026"),
        "DB_NAME": os.getenv("DB_NAME", "ms_reportes"),
        "PRODUCTOS_URL": os.getenv("PRODUCTOS_URL", "http://127.0.0.1:5001").rstrip("/"),
        "RABBITMQ_URL": os.getenv("RABBITMQ_URL", "amqp://inventario:inventario_secret@127.0.0.1:5672/%2F"),
    }
