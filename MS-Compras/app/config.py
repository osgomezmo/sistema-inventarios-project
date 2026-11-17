"""Configuracion centralizada mediante variables de entorno para ms-compras."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

DIRECTORIO_RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(DIRECTORIO_RAIZ / ".env")


@dataclass(frozen=True)
class ConfigCompras:
    """Parametros de configuracion inmutables del microservicio ms-compras."""

    port: int
    flask_debug: bool
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    db_pool_size: int
    rabbitmq_url: str
    rabbitmq_exchange: str
    proveedores_url: str
    proveedores_timeout_seconds: float
    service_token: str


def _parsear_entero_acotado(nombre: str, defecto: str, minimo: int, maximo: int) -> int:
    bruto = os.getenv(nombre, defecto).strip()
    try:
        valor = int(bruto)
    except ValueError as exc:
        raise ValueError(f"La variable {nombre} debe ser un entero valido: {bruto!r}") from exc
    return max(minimo, min(maximo, valor))


def _parsear_flotante_positivo(nombre: str, defecto: str) -> float:
    bruto = os.getenv(nombre, defecto).strip()
    try:
        valor = float(bruto)
    except ValueError as exc:
        raise ValueError(f"La variable {nombre} debe ser numerica: {bruto!r}") from exc
    if valor <= 0:
        raise ValueError(f"La variable {nombre} debe ser mayor que cero: {bruto!r}")
    return valor


def cargar_configuracion() -> ConfigCompras:
    """Carga y valida la configuracion desde variables de entorno."""
    return ConfigCompras(
        port=_parsear_entero_acotado("PORT", "5000", 1, 65535),
        flask_debug=os.getenv("FLASK_DEBUG", "false").strip().lower() == "true",
        db_host=os.getenv("DB_HOST", "127.0.0.1").strip(),
        db_port=_parsear_entero_acotado("DB_PORT", "3306", 1, 65535),
        db_user=os.getenv("DB_USER", "compras_user").strip(),
        db_password=os.getenv("DB_PASSWORD", "changeme"),
        db_name=os.getenv("DB_NAME", "mscompras").strip(),
        db_pool_size=_parsear_entero_acotado("DB_POOL_SIZE", "5", 1, 32),
        rabbitmq_url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@127.0.0.1:5672/").strip(),
        rabbitmq_exchange=os.getenv("RABBITMQ_EXCHANGE", "inventario.eventos").strip(),
        proveedores_url=os.getenv("PROVEEDORES_URL", "http://127.0.0.1:3001").strip().rstrip("/"),
        proveedores_timeout_seconds=_parsear_flotante_positivo(
            "PROVEEDORES_TIMEOUT_SECONDS", "3.0"
        ),
        service_token=os.getenv("SERVICE_TOKEN", "").strip(),
    )
