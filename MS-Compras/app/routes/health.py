"""Rutas de liveness y readiness de ms-compras."""

from flask import Blueprint, jsonify

from app.db import verificar_salud_db
from app.messaging.publicador import verificar_salud_rabbitmq

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def liveness():
    """Sonda liveness sin dependencias externas."""
    return jsonify({"status": "ok", "service": "ms-compras"}), 200


@health_bp.get("/health/ready")
def readiness():
    """Sonda readiness: valida MySQL y RabbitMQ obligatorios para operar."""
    verificar_salud_db()
    verificar_salud_rabbitmq()
    return (
        jsonify(
            {
                "status": "ok",
                "service": "ms-compras",
                "dependencias": {
                    "mysql": "ok",
                    "rabbitmq": "ok",
                },
            }
        ),
        200,
    )
