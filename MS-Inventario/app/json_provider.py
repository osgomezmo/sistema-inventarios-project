from datetime import date, datetime, timezone
from decimal import Decimal

from flask.json.provider import DefaultJSONProvider


def fecha_hora_a_utc(valor):
    if valor.utcoffset() is None:
        valor = valor.replace(tzinfo=timezone.utc)
    utc = valor.astimezone(timezone.utc).replace(tzinfo=None)
    return f"{utc.isoformat(timespec='seconds')}Z"


class ProveedorJson(DefaultJSONProvider):
    def default(self, valor):
        if isinstance(valor, Decimal):
            return float(valor)
        if isinstance(valor, datetime):
            return fecha_hora_a_utc(valor)
        if isinstance(valor, date):
            return valor.isoformat()
        return super().default(valor)
