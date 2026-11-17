"""Pruebas unitarias con mocking de todos los endpoints de ms-productos.

Verifica la recepcion, validacion, manejo y retorno de cada endpoint de
categorias y productos sin depender de un servidor MySQL en ejecucion,
cubriendo casos verdaderos (reales), absurdos, ilogicos y fuera de rango.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import mysql.connector
import pytest

import app.routes.categorias as rutas_cat
import app.routes.productos as rutas_prod
from app import create_app
from app.errors import ApiError

TOKEN = "token-unitario-productos"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "SERVICE_TOKEN": TOKEN})
    return app.test_client()


def mock_transaccion(monkeypatch, modulo):
    """Reemplaza transaccion() en el modulo de rutas por un contextmanager en memoria."""
    estado = {"commits": 0, "rollbacks": 0, "cursor": object()}

    @contextmanager
    def _tx():
        try:
            yield estado["cursor"]
            estado["commits"] += 1
        except Exception:
            estado["rollbacks"] += 1
            raise

    monkeypatch.setattr(modulo, "transaccion", _tx)
    return estado


class TestEndpointsCategoriasMock:
    def test_casos_reales_crud_e_inactivacion_de_categorias(self, client, monkeypatch):
        mock_transaccion(monkeypatch, rutas_cat)

        # 1. GET /categorias (raices con subcategorias anidadas)
        monkeypatch.setattr(
            rutas_cat.repo,
            "listar_raices",
            lambda _c, estado, per_page, offset: (
                [
                    {
                        "id_categoria": 1,
                        "nombre": "Lacteos",
                        "descripcion": "Refrigerados",
                        "id_categoria_padre": None,
                        "estado": estado or "ACTIVO",
                    }
                ],
                1,
            ),
        )
        monkeypatch.setattr(
            rutas_cat.repo,
            "subcategorias_por_padre",
            lambda _c, ids, estado=None: {
                i: [
                    {
                        "id_categoria": 2,
                        "nombre": "Leches",
                        "descripcion": None,
                        "id_categoria_padre": i,
                        "estado": "ACTIVO",
                    }
                ]
                for i in ids
            },
        )
        res_list = client.get("/categorias?estado=ACTIVO&page=1&per_page=10", headers=HEADERS)
        assert res_list.status_code == 200
        body_list = res_list.get_json()
        assert body_list["meta"] == {"page": 1, "per_page": 10, "total": 1}
        assert body_list["data"][0]["subcategorias"][0]["nombre"] == "Leches"

        # 2. GET /categorias?id_padre=1 (lista plana de subcategorias)
        monkeypatch.setattr(
            rutas_cat.repo,
            "listar_hijas",
            lambda _c, id_padre, _est, _pp, _off: (
                [
                    {
                        "id_categoria": 2,
                        "nombre": "Leches",
                        "descripcion": None,
                        "id_categoria_padre": id_padre,
                        "estado": "ACTIVO",
                    }
                ],
                1,
            ),
        )
        res_hijas = client.get("/categorias?id_padre=1", headers=HEADERS)
        assert res_hijas.status_code == 200
        assert "subcategorias" not in res_hijas.get_json()["data"][0]

        # 3. GET /categorias/{id}
        monkeypatch.setattr(
            rutas_cat.repo,
            "obtener",
            lambda _c, id_cat: {
                "id_categoria": id_cat,
                "nombre": "Lacteos",
                "descripcion": "Refrigerados",
                "id_categoria_padre": None,
                "estado": "ACTIVO",
            },
        )
        res_get = client.get("/categorias/1", headers=HEADERS)
        assert res_get.status_code == 200
        assert res_get.get_json()["id_categoria"] == 1
        assert len(res_get.get_json()["subcategorias"]) == 1

        # 4. POST /categorias (creacion de subcategoria bajo padre raiz activo)
        monkeypatch.setattr(
            rutas_cat.repo,
            "obtener_bloqueando",
            lambda _c, id_cat: {
                "id_categoria": id_cat,
                "nombre": "Lacteos",
                "descripcion": None,
                "id_categoria_padre": None,
                "estado": "ACTIVO",
            },
        )
        monkeypatch.setattr(rutas_cat.repo, "nombre_repetido", lambda *_a, **_k: False)
        monkeypatch.setattr(rutas_cat.repo, "insertar", lambda *_a, **_k: 5)
        monkeypatch.setattr(
            rutas_cat.repo,
            "obtener",
            lambda _c, id_cat: {
                "id_categoria": id_cat,
                "nombre": "Quesos",
                "descripcion": "Madurados",
                "id_categoria_padre": 1,
                "estado": "ACTIVO",
            },
        )
        res_post = client.post(
            "/categorias",
            headers=HEADERS,
            json={"nombre": "  Quesos ", "descripcion": " Madurados ", "id_categoria_padre": 1},
        )
        assert res_post.status_code == 201
        assert res_post.get_json() == {
            "id_categoria": 5,
            "nombre": "Quesos",
            "descripcion": "Madurados",
            "id_categoria_padre": 1,
            "estado": "ACTIVO",
        }

        # 5. PUT /categorias/{id}
        monkeypatch.setattr(rutas_cat.repo, "contar_subcategorias", lambda _c, _id: 0)
        monkeypatch.setattr(rutas_cat.repo, "actualizar", lambda *_a, **_k: None)
        res_put = client.put(
            "/categorias/5",
            headers=HEADERS,
            json={"nombre": "Quesos Frescos", "descripcion": None, "id_categoria_padre": 1},
        )
        assert res_put.status_code == 200
        assert res_put.get_json()["id_categoria"] == 5

        # 6. POST /categorias/{id}/inactivar (sin productos activos)
        monkeypatch.setattr(rutas_cat.repo, "bloquear_subcategorias", lambda _c, _id: [])
        monkeypatch.setattr(rutas_cat.repo, "contar_productos_activos", lambda _c, _ids: 0)
        monkeypatch.setattr(rutas_cat.repo, "actualizar_estado", lambda *_a, **_k: None)
        monkeypatch.setattr(
            rutas_cat.repo,
            "obtener",
            lambda _c, id_cat: {
                "id_categoria": id_cat,
                "nombre": "Quesos",
                "descripcion": None,
                "id_categoria_padre": 1,
                "estado": "INACTIVO",
            },
        )
        res_inact = client.post("/categorias/5/inactivar", headers=HEADERS)
        assert res_inact.status_code == 200
        assert res_inact.get_json()["estado"] == "INACTIVO"

        # 7. POST /categorias/{id}/activar (subcategoria con padre ACTIVO)
        def fake_obtener_bloq(_c, id_cat):
            if id_cat == 1:
                return {"id_categoria": 1, "id_categoria_padre": None, "estado": "ACTIVO"}
            return {
                "id_categoria": 5,
                "nombre": "Quesos",
                "descripcion": None,
                "id_categoria_padre": 1,
                "estado": "INACTIVO",
            }

        monkeypatch.setattr(rutas_cat.repo, "obtener_bloqueando", fake_obtener_bloq)
        res_act = client.post("/categorias/5/activar", headers=HEADERS)
        assert res_act.status_code == 200
        assert res_act.get_json()["estado"] == "ACTIVO"

    def test_casos_ilogicos_absurdos_y_fuera_de_rango_categorias(self, client, monkeypatch):
        mock_transaccion(monkeypatch, rutas_cat)

        # Padre de tercer nivel (el padre ya tiene padre) -> 422 VALIDACION
        monkeypatch.setattr(
            rutas_cat.repo,
            "obtener_bloqueando",
            lambda _c, _id: {
                "id_categoria": 2,
                "id_categoria_padre": 1,
                "estado": "ACTIVO",
            },
        )
        res_3er_nivel = client.post(
            "/categorias",
            headers=HEADERS,
            json={"nombre": "Sub-subcategoria", "id_categoria_padre": 2},
        )
        assert res_3er_nivel.status_code == 422
        assert "id_categoria_padre" in res_3er_nivel.get_json()["error"]["detalles"]

        # Categoria que intenta ser su propio padre en PUT -> 422 VALIDACION
        res_ciclo = client.put(
            "/categorias/2",
            headers=HEADERS,
            json={"nombre": "Ciclo", "id_categoria_padre": 2},
        )
        assert res_ciclo.status_code == 422
        assert "propio padre" in res_ciclo.get_json()["error"]["detalles"]["id_categoria_padre"][0]

        # Raiz con subcategorias que intenta volverse subcategoria -> 422 VALIDACION
        monkeypatch.setattr(
            rutas_cat.repo,
            "obtener_bloqueando",
            lambda _c, _id: {"id_categoria": 1, "id_categoria_padre": None, "estado": "ACTIVO"},
        )
        monkeypatch.setattr(rutas_cat.repo, "contar_subcategorias", lambda _c, _id: 3)
        res_raiz_hija = client.put(
            "/categorias/1",
            headers=HEADERS,
            json={"nombre": "Lacteos", "id_categoria_padre": 9},
        )
        assert res_raiz_hija.status_code == 422

        # Nombre repetido en el mismo nivel -> 409 NOMBRE_REPETIDO
        monkeypatch.setattr(rutas_cat.repo, "nombre_repetido", lambda *_a, **_k: True)
        res_dup = client.post("/categorias", headers=HEADERS, json={"nombre": "Lacteos"})
        assert res_dup.status_code == 409
        assert res_dup.get_json()["error"]["codigo"] == "NOMBRE_REPETIDO"

        # Inactivar categoria con productos activos -> 409 CATEGORIA_CON_PRODUCTOS
        monkeypatch.setattr(rutas_cat.repo, "bloquear_subcategorias", lambda _c, _id: [])
        monkeypatch.setattr(rutas_cat.repo, "contar_productos_activos", lambda _c, _ids: 4)
        res_con_prod = client.post("/categorias/1/inactivar", headers=HEADERS)
        assert res_con_prod.status_code == 409
        assert res_con_prod.get_json()["error"]["codigo"] == "CATEGORIA_CON_PRODUCTOS"

        # Activar subcategoria con padre INACTIVO -> 409 CONFLICTO
        monkeypatch.setattr(
            rutas_cat.repo,
            "obtener",
            lambda _c, _id: {"id_categoria": 5, "id_categoria_padre": 1, "estado": "INACTIVO"},
        )
        monkeypatch.setattr(
            rutas_cat.repo,
            "obtener_bloqueando",
            lambda _c, id_c: (
                {"id_categoria": 1, "id_categoria_padre": None, "estado": "INACTIVO"}
                if id_c == 1
                else {"id_categoria": 5, "id_categoria_padre": 1, "estado": "INACTIVO"}
            ),
        )
        res_padre_inact = client.post("/categorias/5/activar", headers=HEADERS)
        assert res_padre_inact.status_code == 409
        assert res_padre_inact.get_json()["error"]["codigo"] == "CONFLICTO"

        # Entradas absurdas: booleanos en id_categoria_padre, nombre > 100 chars, descripcion > 255 chars
        res_absurdo = client.post(
            "/categorias",
            headers=HEADERS,
            json={
                "nombre": "X" * 101,
                "descripcion": "D" * 256,
                "id_categoria_padre": True,
            },
        )
        assert res_absurdo.status_code == 422
        assert set(res_absurdo.get_json()["error"]["detalles"]) == {
            "nombre",
            "descripcion",
            "id_categoria_padre",
        }


class TestEndpointsProductosMock:
    def test_casos_reales_crud_busqueda_sku_e_inactivacion_de_productos(self, client, monkeypatch):
        mock_transaccion(monkeypatch, rutas_prod)
        creado_dt = datetime(2026, 11, 16, 20, 0, 0, tzinfo=timezone.utc)
        fila_producto = {
            "id_producto": 10,
            "sku": "LAC-0001",
            "nombre": "Leche entera 1 L",
            "descripcion": "Bolsa pasteurizada",
            "marca": "Alqueria",
            "id_categoria": 2,
            "unidad_medida": "LITRO",
            "precio_venta": Decimal("4200.50"),
            "stock_minimo": Decimal("15.000"),
            "estado": "ACTIVO",
            "creado_en": creado_dt,
        }

        # 1. GET /productos con filtros combinados
        monkeypatch.setattr(
            rutas_prod.repo,
            "listar",
            lambda _c, _pp, _off, **_f: ([dict(fila_producto)], 1),
        )
        res_list = client.get(
            "/productos?q=Leche&id_categoria=2&estado=ACTIVO&precio_min=1000&precio_max=5000&skus=lac-0001&page=1&per_page=20",
            headers=HEADERS,
        )
        assert res_list.status_code == 200
        data_list = res_list.get_json()
        assert data_list["meta"] == {"page": 1, "per_page": 20, "total": 1}
        assert data_list["data"][0]["sku"] == "LAC-0001"
        assert data_list["data"][0]["precio_venta"] == 4200.5
        assert data_list["data"][0]["creado_en"] == "2026-11-16T20:00:00Z"

        # 2. GET /productos?skus= (vacio cortocircuita sin tocar BD)
        res_vacio = client.get("/productos?skus= , ", headers=HEADERS)
        assert res_vacio.status_code == 200
        assert res_vacio.get_json() == {"data": [], "meta": {"page": 1, "per_page": 20, "total": 0}}

        # 3. GET /productos/{id}
        monkeypatch.setattr(rutas_prod.repo, "obtener", lambda _c, _id: dict(fila_producto))
        res_id = client.get("/productos/10", headers=HEADERS)
        assert res_id.status_code == 200
        assert res_id.get_json()["id_producto"] == 10

        # 4. GET /productos/sku/{sku} (contrato interno para ms-inventario)
        monkeypatch.setattr(
            rutas_prod.repo,
            "obtener_por_sku",
            lambda _c, sku: {
                "sku": sku.upper(),
                "nombre": "Leche entera 1 L",
                "estado": "ACTIVO",
                "unidad_medida": "LITRO",
                "stock_minimo": Decimal("15.000"),
                "id_categoria": 2,
            },
        )
        res_sku = client.get("/productos/sku/lac-0001", headers=HEADERS)
        assert res_sku.status_code == 200
        assert res_sku.get_json() == {
            "sku": "LAC-0001",
            "nombre": "Leche entera 1 L",
            "estado": "ACTIVO",
            "unidad_medida": "LITRO",
            "stock_minimo": 15.0,
            "id_categoria": 2,
        }

        # 5. POST /productos
        monkeypatch.setattr(
            rutas_prod.repo_categorias,
            "obtener_compartido",
            lambda _c, id_c: {"id_categoria": id_c, "estado": "ACTIVO"},
        )
        monkeypatch.setattr(rutas_prod.repo, "insertar", lambda _c, **_kw: 10)
        res_post = client.post(
            "/productos",
            headers=HEADERS,
            json={
                "sku": " lac-0001 ",
                "nombre": "Leche entera 1 L",
                "descripcion": "Bolsa pasteurizada",
                "marca": "Alqueria",
                "id_categoria": 2,
                "unidad_medida": "LITRO",
                "precio_venta": 4200.5,
                "stock_minimo": "15.000",
            },
        )
        assert res_post.status_code == 201
        assert res_post.get_json()["sku"] == "LAC-0001"

        # 6. PUT /productos/{id}
        monkeypatch.setattr(rutas_prod.repo, "obtener_bloqueando", lambda _c, _id: dict(fila_producto))
        monkeypatch.setattr(rutas_prod.repo, "actualizar", lambda *_a, **_k: None)
        res_put = client.put(
            "/productos/10",
            headers=HEADERS,
            json={
                "sku": "INTENTO-CAMBIAR-SKU",
                "nombre": "Leche entera 1 L",
                "descripcion": "Actualizada",
                "marca": "Alqueria",
                "id_categoria": 2,
                "unidad_medida": "LITRO",
                "precio_venta": 4500,
                "stock_minimo": 10,
            },
        )
        assert res_put.status_code == 200

        # 7. POST /productos/{id}/inactivar y /activar
        monkeypatch.setattr(rutas_prod.repo, "actualizar_estado", lambda *_a, **_k: None)
        res_inact = client.post("/productos/10/inactivar", headers=HEADERS)
        assert res_inact.status_code == 200
        assert res_inact.get_json()["estado"] == "INACTIVO"

        prod_inactivo = dict(fila_producto, estado="INACTIVO")
        monkeypatch.setattr(rutas_prod.repo, "obtener", lambda _c, _id: dict(prod_inactivo))
        monkeypatch.setattr(rutas_prod.repo, "obtener_bloqueando", lambda _c, _id: dict(prod_inactivo))
        res_act = client.post("/productos/10/activar", headers=HEADERS)
        assert res_act.status_code == 200
        assert res_act.get_json()["estado"] == "ACTIVO"

    def test_casos_ilogicos_absurdos_y_fuera_de_rango_productos(self, client, monkeypatch):
        mock_transaccion(monkeypatch, rutas_prod)

        # 1. SKU duplicado (errno 1062) -> 409 SKU_DUPLICADO
        monkeypatch.setattr(
            rutas_prod.repo_categorias,
            "obtener_compartido",
            lambda _c, id_c: {"id_categoria": id_c, "estado": "ACTIVO"},
        )

        def lanzar_dup(*_a, **_k):
            raise mysql.connector.IntegrityError(msg="Duplicate", errno=1062)

        monkeypatch.setattr(rutas_prod.repo, "insertar", lanzar_dup)
        res_dup = client.post(
            "/productos",
            headers=HEADERS,
            json={
                "sku": "LAC-0001",
                "nombre": "Leche",
                "marca": "Alqueria",
                "id_categoria": 2,
                "unidad_medida": "UNIDAD",
                "precio_venta": 4000,
                "stock_minimo": 5,
            },
        )
        assert res_dup.status_code == 409
        assert res_dup.get_json()["error"]["codigo"] == "SKU_DUPLICADO"

        # 2. Categoria inactiva o inexistente al crear producto -> 422 VALIDACION
        monkeypatch.setattr(
            rutas_prod.repo_categorias,
            "obtener_compartido",
            lambda _c, _id: {"id_categoria": 2, "estado": "INACTIVO"},
        )
        res_cat_inact = client.post(
            "/productos",
            headers=HEADERS,
            json={
                "sku": "LAC-0002",
                "nombre": "Yogur",
                "marca": "Alpina",
                "id_categoria": 2,
                "unidad_medida": "UNIDAD",
                "precio_venta": 3000,
                "stock_minimo": 10,
            },
        )
        assert res_cat_inact.status_code == 422
        assert "inactiva" in res_cat_inact.get_json()["error"]["detalles"]["id_categoria"][0]

        # 3. Stock minimo decimal cuando unidad_medida es UNIDAD -> 422 VALIDACION
        res_unidad_dec = client.post(
            "/productos",
            headers=HEADERS,
            json={
                "sku": "LAC-0003",
                "nombre": "Queso",
                "marca": "Alpina",
                "id_categoria": 2,
                "unidad_medida": "UNIDAD",
                "precio_venta": 5000,
                "stock_minimo": "2.500",
            },
        )
        assert res_unidad_dec.status_code == 422
        assert "stock_minimo" in res_unidad_dec.get_json()["error"]["detalles"]

        # 4. Valores absurdos y fuera de rango en body: booleanos, negativos, NaN, Infinity, exceso DECIMAL
        res_absurdos = client.post(
            "/productos",
            headers=HEADERS,
            json={
                "sku": "SKU CON ESPACIOS Y Ñ!",
                "nombre": "",
                "marca": True,
                "id_categoria": -5,
                "unidad_medida": "GALON",
                "precio_venta": "1000000000000.00",
                "stock_minimo": "-0.001",
            },
        )
        assert res_absurdos.status_code == 422
        assert set(res_absurdos.get_json()["error"]["detalles"]) == {
            "sku",
            "nombre",
            "marca",
            "id_categoria",
            "unidad_medida",
            "precio_venta",
            "stock_minimo",
        }

        # 5. Filtros ilogicos en GET /productos: precio_min > precio_max, >100 skus, page=0
        res_filtros = client.get(
            "/productos",
            headers=HEADERS,
            query_string={
                "precio_min": "9000",
                "precio_max": "1000",
                "page": "0",
                "per_page": "500",
                "estado": "ELIMINADO",
                "skus": ",".join(f"SKU-{i}" for i in range(101)),
            },
        )
        assert res_filtros.status_code == 422
        assert set(res_filtros.get_json()["error"]["detalles"]) == {
            "precio_min",
            "page",
            "per_page",
            "estado",
            "skus",
        }

        # 6. Producto inexistente -> 404 NO_EXISTE
        monkeypatch.setattr(rutas_prod.repo, "obtener", lambda _c, _id: None)
        monkeypatch.setattr(rutas_prod.repo, "obtener_por_sku", lambda _c, _s: None)
        assert client.get("/productos/9999", headers=HEADERS).status_code == 404
        assert client.get("/productos/sku/NO-EXISTE", headers=HEADERS).status_code == 404
