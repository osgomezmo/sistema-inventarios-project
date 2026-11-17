"""Proveedor JSON personalizado para Decimal y marcas de tiempo UTC."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from flask.json.provider import DefaultJSONProvider


class ProveedorJSONCompras(DefaultJSONProvider):
    """Serializa Decimal como numero JSON y datetime en ISO-8601 UTC con sufijo Z."""

    @staticmethod
    def default(o: Any) -> Any:
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, datetime):
            if o.tzinfo is None:
                dt_utc = o.replace(tzinfo=timezone.utc)
            else:
                dt_utc = o.astimezone(timezone.utc)
            return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        if isinstance(o, date):
            return o.isoformat()
        return super().default(o)
