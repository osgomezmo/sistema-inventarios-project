"""Cliente HTTP síncrono hacia ms-productos con requests."""

import logging
import os
import uuid
import requests
from flask import current_app, g, has_app_context

from app.errors import ApiError

logger = logging.getLogger("productos_client")

_catalogo_mock = None


def set_catalogo_mock(mock):
    """Permite inyectar un catálogo simulado en pruebas unitarias."""
    global _catalogo_mock
    _catalogo_mock = mock


def obtener_catalogo_productos(requerido=False, config=None):
    """Consulta síncronamente ms-productos y devuelve un dict indexado por SKU.

    Retorna: { sku: { 'nombre': ..., 'id_categoria': ..., 'categoria_nombre': ... } }
    Si falla y requerido=True (o STRICT_PRODUCTS_CHECK=true), lanza 503 SERVICIO_NO_DISPONIBLE.
    Si falla y requerido=False, retorna dict vacío para modo tolerante.
    """
    if _catalogo_mock is not None:
        if isinstance(_catalogo_mock, Exception):
            if requerido or os.getenv("STRICT_PRODUCTS_CHECK", "").lower() in ("true", "1"):
                raise ApiError(
                    "SERVICIO_NO_DISPONIBLE",
                    "El microservicio de productos no está disponible.",
                    503,
                )
            return {}
        return _catalogo_mock

    cfg = config
    if cfg is None:
        if has_app_context():
            cfg = current_app.config
        else:
            from app.config import cargar_configuracion
            cfg = cargar_configuracion()

    base_url = cfg.get("PRODUCTOS_URL", "http://127.0.0.1:5001").rstrip("/")
    token = cfg.get("SERVICE_TOKEN", "")

    correlation_id = getattr(g, "correlation_id", str(uuid.uuid4())) if has_app_context() else str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Correlation-Id": correlation_id,
        "Accept": "application/json",
    }

    try:
        # 1. Consultar categorías para mapear id_categoria -> categoria_nombre
        nombres_categorias = {}
        try:
            res_cat = requests.get(f"{base_url}/categorias?per_page=100", headers=headers, timeout=5.0)
            if res_cat.status_code == 200:
                cat_json = res_cat.json()
                items_cat = cat_json.get("data", []) if isinstance(cat_json, dict) else cat_json
                for cat in items_cat:
                    nombres_categorias[cat["id_categoria"]] = cat.get("nombre", "Sin categoría")
        except Exception as e:
            logger.warning("No se pudo obtener listado de categorías de ms-productos: %s", e)

        # 2. Consultar productos
        res_prod = requests.get(f"{base_url}/productos?per_page=100", headers=headers, timeout=5.0)
        if res_prod.status_code != 200:
            raise requests.RequestException(f"Respuesta {res_prod.status_code} desde ms-productos")

        prod_json = res_prod.json()
        items_prod = prod_json.get("data", []) if isinstance(prod_json, dict) else prod_json

        catalogo = {}
        for p in items_prod:
            sku = p.get("sku")
            if not sku:
                continue
            id_cat = p.get("id_categoria")
            catalogo[sku] = {
                "nombre": p.get("nombre", sku),
                "id_categoria": id_cat,
                "categoria_nombre": nombres_categorias.get(id_cat, "Sin categoría"),
            }
        return catalogo

    except Exception as err:
        logger.error("Error al consultar ms-productos: %s", err)
        es_estricto = requerido or os.getenv("STRICT_PRODUCTS_CHECK", "").lower() in ("true", "1")
        if es_estricto:
            raise ApiError(
                "SERVICIO_NO_DISPONIBLE",
                "El microservicio de productos no está disponible.",
                503,
            ) from None
        return {}
