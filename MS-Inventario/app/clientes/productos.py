"""Cliente HTTP de ms-productos (D39).

Consulta GET /productos/sku/{sku} con el token de servicio, antes de abrir la
transacción del movimiento (D22). Solo usa la biblioteca estándar.
"""

import json
from decimal import Decimal
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from flask import current_app

from app.errors import ApiError

INTENTOS = 2  # la llamada original y un reintento
CAMPOS_TEXTO = ("sku", "nombre", "estado", "unidad_medida")


def _no_disponible():
    return ApiError("SERVICIO_NO_DISPONIBLE", "El servicio de productos no responde.", 503)


def _producto_inexistente():
    return ApiError("PRODUCTO_INEXISTENTE", "El producto no existe.", 404)


def _registrar(motivo, intento=None):
    # Mensaje corto: nunca el token, las cabeceras ni la URL completa.
    if intento is None:
        current_app.logger.warning("ms-productos: %s, sin reintento", motivo)
    else:
        current_app.logger.warning("ms-productos: %s (intento %s de %s)", motivo, intento, INTENTOS)


def _leer_producto(cuerpo):
    """Valida el JSON de ms-productos y devuelve solo los campos que se usan."""
    try:
        datos = json.loads(cuerpo, parse_float=Decimal)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(datos, dict):
        return None
    if not all(isinstance(datos.get(c), str) for c in CAMPOS_TEXTO):
        return None
    stock_minimo, id_categoria = datos.get("stock_minimo"), datos.get("id_categoria")
    if isinstance(stock_minimo, bool) or not isinstance(stock_minimo, (int, Decimal)):
        return None
    if isinstance(id_categoria, bool) or not isinstance(id_categoria, int):
        return None
    producto = {c: datos[c] for c in CAMPOS_TEXTO}
    producto["stock_minimo"] = Decimal(stock_minimo)
    producto["id_categoria"] = id_categoria
    return producto


def consultar_producto(sku, id_correlacion=None, *, base_url=None, token=None, timeout=None):
    """Devuelve {sku, nombre, estado, unidad_medida, stock_minimo, id_categoria}.

    404 de ms-productos: ApiError PRODUCTO_INEXISTENTE. Cualquier otra falla
    (red, timeout, 5xx tras un reintento, 4xx, cuerpo inválido): ApiError
    SERVICIO_NO_DISPONIBLE 503. Un producto INACTIVO se acepta (D6).
    """
    config = current_app.config
    base_url = (base_url or config["PRODUCTOS_URL"]).rstrip("/")
    token = config["SERVICE_TOKEN"] if token is None else token
    timeout = config["PRODUCTOS_TIMEOUT"] if timeout is None else timeout

    cabeceras = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if id_correlacion:
        cabeceras["X-Correlation-Id"] = id_correlacion
    peticion = Request(f"{base_url}/productos/sku/{quote(sku, safe='')}", headers=cabeceras)

    for intento in range(1, INTENTOS + 1):
        try:
            with urlopen(peticion, timeout=timeout) as respuesta:
                cuerpo = respuesta.read()
        except HTTPError as error:
            if error.code == 404:
                raise _producto_inexistente() from None
            if error.code >= 500:
                _registrar(f"respuesta {error.code}", intento)
                continue
            # 4xx distinto de 404: reintentar no lo arregla.
            _registrar(f"respuesta {error.code}")
            raise _no_disponible() from None
        except (URLError, TimeoutError, OSError, HTTPException):
            _registrar("sin respuesta o timeout", intento)
            continue

        producto = _leer_producto(cuerpo)
        if producto is None:
            _registrar("respuesta con formato inesperado")
            raise _no_disponible()
        return producto

    raise _no_disponible()
