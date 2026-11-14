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
        # ms-productos, para validar el SKU antes de cada movimiento (D39)
        "PRODUCTOS_URL": os.getenv("PRODUCTOS_URL", "http://127.0.0.1:5001").rstrip("/"),
        "PRODUCTOS_TIMEOUT": float(os.getenv("PRODUCTOS_TIMEOUT", "3.0")),
        # RabbitMQ (D48): vacío desactiva la publicación; RABBITMQ_HOST reemplaza el host
        "RABBITMQ_URL": os.getenv("RABBITMQ_URL", "").strip(),
        "RABBITMQ_HOST": os.getenv("RABBITMQ_HOST", "").strip(),
    }
