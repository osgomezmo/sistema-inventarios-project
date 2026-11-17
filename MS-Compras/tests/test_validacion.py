"""Pruebas unitarias de validadores, paginacion, roles y serializacion JSON."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.auth import normalizar_rol
from app.errors import ErrorAPI
from app.json_provider import ProveedorJSONCompras
from app.paginacion import construir_meta, obtener_parametros_paginacion
from app.validacion import (
    parsear_fecha_filtro,
    validar_anulacion_payload,
    validar_devolucion_payload,
    validar_orden_payload,
    validar_recepcion_payload,
)


class TestCasosReales:
    def test_valida_orden_con_decimal_alias_cantidad_y_normalizacion_sku(self):
        resultado = validar_orden_payload(
            {
                "id_proveedor": 3,
                "id_bodega_destino": 1,
                "items": [
                    {"sku": "  arroz-5kg ", "cantidad": "12.5", "precio_unitario": 18500.75},
                    {"sku": "aceite-1l", "cantidad_pedida": 4, "precio_unitario": "9200.1"},
                ],
            }
        )

        assert resultado["id_proveedor"] == 3
        assert resultado["id_bodega_destino"] == 1
        assert resultado["items"] == [
            {
                "sku": "ARROZ-5KG",
                "cantidad_pedida": Decimal("12.500"),
                "precio_unitario": Decimal("18500.75"),
            },
            {
                "sku": "ACEITE-1L",
                "cantidad_pedida": Decimal("4.000"),
                "precio_unitario": Decimal("9200.10"),
            },
        ]

    def test_valida_recepcion_devolucion_y_anulacion_correctas(self):
        recep = validar_recepcion_payload(
            {
                "observaciones": "  Entrega completa en muelle 2  ",
                "items": [{"id_detalle": 10, "cantidad": "5.250"}],
            }
        )
        assert recep["observaciones"] == "Entrega completa en muelle 2"
        assert recep["items"] == [{"id_detalle": 10, "cantidad": Decimal("5.250")}]

        dev = validar_devolucion_payload(
            {
                "motivo": "  Producto vencido  ",
                "items": [{"id_detalle": 10, "cantidad": 2}],
            }
        )
        assert dev["motivo"] == "Producto vencido"
        assert dev["items"] == [{"id_detalle": 10, "cantidad": Decimal("2.000")}]

        assert validar_anulacion_payload({"motivo": " Cambio de proveedor "}) == "Cambio de proveedor"

    def test_serializador_json_roles_paginacion_y_fechas_utc(self, app):
        assert normalizar_rol("Jefe") == "jefe_bodega"
        assert normalizar_rol("jefe_de_bodega") == "jefe_bodega"
        assert normalizar_rol("COMPRAS") == "compras"

        dt_naive = datetime(2026, 11, 14, 15, 30, 0)
        assert ProveedorJSONCompras.default(dt_naive) == "2026-11-14T15:30:00Z"
        assert ProveedorJSONCompras.default(Decimal("1250.50")) == 1250.5

        desde = parsear_fecha_filtro("2026-11-01", "desde", fin_de_dia=False)
        hasta = parsear_fecha_filtro("2026-11-14", "hasta", fin_de_dia=True)
        assert desde == datetime(2026, 11, 1, 0, 0, 0)
        assert hasta == datetime(2026, 11, 14, 23, 59, 59)

        with app.test_request_context("/ordenes-compra?page=3&per_page=25"):
            assert obtener_parametros_paginacion() == (3, 25, 50)
        assert construir_meta(51, 3, 25) == {
            "page": 3,
            "per_page": 25,
            "total": 51,
            "total_pages": 3,
        }


class TestCasosIlogicos:
    def test_rechaza_orden_sin_items_o_con_sku_duplicado_por_capitalizacion(self):
        with pytest.raises(ErrorAPI) as exc_vacia:
            validar_orden_payload({"id_proveedor": 1, "id_bodega_destino": 1, "items": []})
        assert exc_vacia.value.status_code == 422

        with pytest.raises(ErrorAPI) as exc_dup:
            validar_orden_payload(
                {
                    "id_proveedor": 1,
                    "id_bodega_destino": 1,
                    "items": [
                        {"sku": "sku-100", "cantidad": 2, "precio_unitario": 500},
                        {"sku": "SKU-100", "cantidad": 3, "precio_unitario": 500},
                    ],
                }
            )
        assert exc_dup.value.status_code == 422
        assert "items[1].sku" in exc_dup.value.detalles

    def test_rechaza_booleanos_y_flotantes_como_identificadores_enteros(self):
        for bad_id in (True, False, 1.9, "1.5", "abc"):
            with pytest.raises(ErrorAPI) as exc:
                validar_orden_payload(
                    {
                        "id_proveedor": bad_id,
                        "id_bodega_destino": 1,
                        "items": [{"sku": "SKU-1", "cantidad": 1, "precio_unitario": 10}],
                    }
                )
            assert exc.value.status_code == 422
            assert "id_proveedor" in exc.value.detalles

    def test_rechaza_id_detalle_duplicado_y_motivo_en_blanco(self):
        with pytest.raises(ErrorAPI) as exc_rec:
            validar_recepcion_payload(
                {
                    "items": [
                        {"id_detalle": 4, "cantidad": 1},
                        {"id_detalle": 4, "cantidad": 2},
                    ]
                }
            )
        assert exc_rec.value.status_code == 422
        assert "items[1].id_detalle" in exc_rec.value.detalles

        with pytest.raises(ErrorAPI) as exc_dev:
            validar_devolucion_payload(
                {
                    "motivo": "   ",
                    "items": [
                        {"id_detalle": 4, "cantidad": 1},
                        {"id_detalle": 4, "cantidad": 1},
                    ],
                }
            )
        assert exc_dev.value.status_code == 422
        assert "motivo" in exc_dev.value.detalles
        assert "items[1].id_detalle" in exc_dev.value.detalles

        with pytest.raises(ErrorAPI):
            validar_anulacion_payload({"motivo": ""})

    def test_rechaza_formato_fecha_invalido_y_observaciones_no_string(self):
        with pytest.raises(ErrorAPI) as exc_fecha:
            parsear_fecha_filtro("14/11/2026", "desde", fin_de_dia=False)
        assert exc_fecha.value.status_code == 422

        with pytest.raises(ErrorAPI) as exc_obs:
            validar_recepcion_payload(
                {"observaciones": 12345, "items": [{"id_detalle": 1, "cantidad": 1}]}
            )
        assert exc_obs.value.status_code == 422


class TestCasosFueraDeRango:
    def test_rechaza_cantidades_y_precios_cero_negativos_nan_infinito_o_subminimos(self):
        valores_invalidos = [0, -1, "-0.5", "0.0001", "NaN", "Infinity", 1e25]
        for val in valores_invalidos:
            with pytest.raises(ErrorAPI) as exc:
                validar_orden_payload(
                    {
                        "id_proveedor": 1,
                        "id_bodega_destino": 1,
                        "items": [{"sku": "SKU-1", "cantidad": val, "precio_unitario": 100}],
                    }
                )
            assert exc.value.status_code == 422

        for precio_malo in (0, -50, "0.001", "1000000000000.00", True):
            with pytest.raises(ErrorAPI) as exc_p:
                validar_orden_payload(
                    {
                        "id_proveedor": 1,
                        "id_bodega_destino": 1,
                        "items": [{"sku": "SKU-1", "cantidad": 1, "precio_unitario": precio_malo}],
                    }
                )
            assert exc_p.value.status_code == 422

    def test_rechaza_ids_desbordados_y_cadenas_sobre_limite_varchar(self):
        for id_fuera in (0, -10, 2_147_483_648):
            with pytest.raises(ErrorAPI):
                validar_orden_payload(
                    {
                        "id_proveedor": id_fuera,
                        "id_bodega_destino": 1,
                        "items": [{"sku": "SKU-1", "cantidad": 1, "precio_unitario": 10}],
                    }
                )

        with pytest.raises(ErrorAPI) as exc_sku:
            validar_orden_payload(
                {
                    "id_proveedor": 1,
                    "id_bodega_destino": 1,
                    "items": [{"sku": "S" * 51, "cantidad": 1, "precio_unitario": 10}],
                }
            )
        assert exc_sku.value.status_code == 422

        with pytest.raises(ErrorAPI):
            validar_anulacion_payload({"motivo": "M" * 256})

        with pytest.raises(ErrorAPI):
            validar_recepcion_payload(
                {"observaciones": "O" * 301, "items": [{"id_detalle": 1, "cantidad": 1}]}
            )

    def test_rechaza_paginacion_fuera_de_rango(self, app):
        for qs in ("page=0", "page=-3", "per_page=0", "per_page=101", "page=abc"):
            with app.test_request_context(f"/ordenes-compra?{qs}"):
                with pytest.raises(ErrorAPI) as exc:
                    obtener_parametros_paginacion()
                assert exc.value.status_code == 422
                assert exc.value.codigo == "VALIDACION"
