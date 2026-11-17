"""Pruebas del motor de movimientos (D41) contra el MySQL de desarrollo.

Las bodegas usan el prefijo de código PREFIJO_BODEGA y los SKU el prefijo
PREFIJO_SKU. Un fixture borra al terminar solo esas filas, en este orden:
movimientos, traslados, saldos y bodegas. El borrado de movimientos existe solo
en las pruebas: la app nunca borra ni modifica el kardex. Si MySQL no está
disponible, las pruebas se saltan.
"""

import random
import re
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

import pytest

from app.config import cargar_configuracion
from app.db import abrir_conexion, ejecutar_con_reintento, transaccion
from app.errors import ApiError
from app.servicios.movimientos import aplicar_movimiento, costo_ponderado

PREFIJO_BODEGA = "ZZT-"
PREFIJO_SKU = "ZZTEST-"
SKU = PREFIJO_SKU + "001"
CONFIG = cargar_configuracion()
ENTRADAS = {"ENTRADA_COMPRA", "AJUSTE_POSITIVO", "TRASLADO_ENTRADA", "DEVOLUCION_CLIENTE"}
CAMPOS_MOVIMIENTO = {
    "id_movimiento", "sku", "id_bodega", "tipo", "cantidad", "costo_unitario",
    "saldo_resultante", "costo_promedio", "valor_resultante", "motivo",
    "documento_referencia", "id_usuario", "id_traslado", "fecha",
}


def patron_like(prefijo):
    # En LIKE, "_" y "%" son comodines: se escapan para filtrar solo el prefijo exacto.
    return prefijo.replace("\\", "\\\\").replace("_", "\\_").replace("%", "\\%") + "%"


def borrar_datos_de_prueba():
    sku, bodega = patron_like(PREFIJO_SKU), patron_like(PREFIJO_BODEGA)
    with transaccion(CONFIG) as cur:
        cur.execute("DELETE FROM movimientos WHERE sku LIKE %s", (sku,))
        cur.execute("DELETE FROM traslados WHERE sku LIKE %s", (sku,))
        cur.execute("DELETE FROM saldos WHERE sku LIKE %s", (sku,))
        cur.execute("DELETE FROM bodegas WHERE codigo LIKE %s", (bodega,))


@pytest.fixture(scope="module", autouse=True)
def mysql_disponible():
    try:
        abrir_conexion(CONFIG).close()
    except ApiError:
        pytest.skip("MySQL de desarrollo no disponible en 127.0.0.1:33062")


@pytest.fixture(autouse=True)
def limpiar():
    borrar_datos_de_prueba()
    yield
    borrar_datos_de_prueba()


def crear_bodega(codigo="B1", estado="ACTIVO"):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO bodegas (codigo, nombre, direccion, estado) VALUES (%s, %s, %s, %s)",
            (PREFIJO_BODEGA + codigo, f"Bodega {codigo}", "Calle 1", estado),
        )
        return cur.lastrowid


@pytest.fixture
def bodega():
    return crear_bodega()


def aplicar(id_bodega, tipo, cantidad, costo=None, *, sku=SKU, unidad="KILO", minimo="0",
            motivo="Ajuste de prueba", **extra):
    """Aplica un movimiento en su propia transacción, como lo hará un endpoint."""
    with transaccion(CONFIG) as cur:
        return aplicar_movimiento(
            cur, sku=sku, id_bodega=id_bodega, tipo=tipo, cantidad=D(cantidad),
            id_usuario=7, unidad_medida=unidad, stock_minimo=D(minimo),
            costo_unitario=None if costo is None else D(costo), motivo=motivo, **extra,
        )


def error_de(*args, **kwargs):
    with pytest.raises(ApiError) as info:
        aplicar(*args, **kwargs)
    return info.value


def saldo(id_bodega, sku=SKU):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "SELECT cantidad, costo_promedio, stock_minimo, actualizado_en,"
            " ROUND(cantidad * costo_promedio, 2) AS valor"
            " FROM saldos WHERE sku = %s AND id_bodega = %s",
            (sku, id_bodega),
        )
        return cur.fetchone()


def kardex(id_bodega, sku=SKU):
    with transaccion(CONFIG) as cur:
        cur.execute(
            "SELECT * FROM movimientos WHERE sku = %s AND id_bodega = %s ORDER BY id_movimiento",
            (sku, id_bodega),
        )
        return cur.fetchall()


def verificar_cadena(filas):
    """Cada fila parte del saldo y costo de la anterior, según la fórmula del motor."""
    saldo_previo, costo_previo = D("0"), D("0")
    for fila in filas:
        if fila["tipo"] in ENTRADAS:
            assert fila["saldo_resultante"] == saldo_previo + fila["cantidad"]
            assert fila["costo_promedio"] == costo_ponderado(
                saldo_previo, costo_previo, fila["cantidad"], fila["costo_unitario"])
        else:
            assert fila["saldo_resultante"] == saldo_previo - fila["cantidad"]
            assert fila["costo_promedio"] == costo_previo
        assert fila["saldo_resultante"] >= 0
        saldo_previo, costo_previo = fila["saldo_resultante"], fila["costo_promedio"]
    return saldo_previo


def verificar_422(error, *campos):
    assert (error.status, error.codigo) == (422, "VALIDACION")
    assert set(error.detalles) == set(campos)


# --- Entradas y costo ponderado ---------------------------------------------------


def test_entrada_sobre_saldo_nuevo(bodega):
    resultado = aplicar(bodega, "ENTRADA_COMPRA", "10", "100.0000")
    movimiento = resultado["movimiento"]
    assert (movimiento["saldo_resultante"], movimiento["costo_promedio"]) == (D("10"), D("100"))
    assert movimiento["valor_resultante"] == D("1000.00")
    assert resultado["saldo_anterior"] == 0
    fila = saldo(bodega)
    assert (fila["cantidad"], fila["costo_promedio"], fila["valor"]) == (D("10"), D("100"), D("1000"))


@pytest.mark.parametrize(
    "primera, segunda, esperado",
    [
        (("10", "100.0000"), ("5", "130.0000"), "110.0000"),
        (("2", "10.0000"), ("1", "11.0000"), "10.3333"),
        (("1", "1.0000"), ("1", "1.0001"), "1.0001"),
    ],
)
def test_costo_ponderado(bodega, primera, segunda, esperado):
    aplicar(bodega, "ENTRADA_COMPRA", *primera)
    movimiento = aplicar(bodega, "ENTRADA_COMPRA", *segunda)["movimiento"]
    assert movimiento["costo_promedio"] == D(esperado)
    assert saldo(bodega)["costo_promedio"] == D(esperado)


# --- Salidas ------------------------------------------------------------------------


def test_salida_al_costo_vigente_ignorando_el_costo_recibido(bodega):
    aplicar(bodega, "ENTRADA_COMPRA", "10", "100.0000")
    movimiento = aplicar(bodega, "SALIDA", "3", "999.9999")["movimiento"]
    assert movimiento["costo_unitario"] == D("100.0000")
    assert movimiento["saldo_resultante"] == D("7")
    assert movimiento["costo_promedio"] == D("100.0000")
    assert movimiento["valor_resultante"] == D("700.00")


def test_salida_exacta_a_cero_conserva_el_costo_y_la_siguiente_entrada_toma_el_nuevo(bodega):
    aplicar(bodega, "ENTRADA_COMPRA", "4", "25.5000")
    movimiento = aplicar(bodega, "SALIDA", "4")["movimiento"]
    assert movimiento["saldo_resultante"] == 0
    assert movimiento["valor_resultante"] == D("0.00")
    assert saldo(bodega)["costo_promedio"] == D("25.5000")

    entrada = aplicar(bodega, "ENTRADA_COMPRA", "2", "40.0000")["movimiento"]
    assert entrada["costo_promedio"] == D("40.0000")


def test_salida_mayor_que_el_saldo_no_escribe_nada(bodega):
    aplicar(bodega, "ENTRADA_COMPRA", "5", "10.0000")
    error = error_de(bodega, "SALIDA", "5.001")
    assert (error.status, error.codigo) == (409, "STOCK_INSUFICIENTE")
    assert list(error.detalles) == ["cantidad"]
    assert len(kardex(bodega)) == 1
    assert saldo(bodega)["cantidad"] == D("5")


def test_salida_sin_saldo_da_409_y_no_crea_el_saldo(bodega):
    error = error_de(bodega, "SALIDA", "1")
    assert (error.status, error.codigo) == (409, "STOCK_INSUFICIENTE")
    assert saldo(bodega) is None
    assert kardex(bodega) == []


# --- Ajustes, devoluciones y traslados ----------------------------------------------


def test_ajuste_positivo_sin_costo_usa_el_vigente(bodega):
    aplicar(bodega, "ENTRADA_COMPRA", "10", "50.0000")
    movimiento = aplicar(bodega, "AJUSTE_POSITIVO", "5")["movimiento"]
    assert movimiento["costo_unitario"] == D("50.0000")
    assert movimiento["costo_promedio"] == D("50.0000")
    assert movimiento["saldo_resultante"] == D("15")


def test_ajuste_positivo_con_saldo_cero_exige_costo(bodega):
    verificar_422(error_de(bodega, "AJUSTE_POSITIVO", "5"), "costo_unitario")
    assert saldo(bodega) is None and kardex(bodega) == []
    movimiento = aplicar(bodega, "AJUSTE_POSITIVO", "5", "12.0000")["movimiento"]
    assert movimiento["costo_promedio"] == D("12.0000")


@pytest.mark.parametrize("tipo", ["AJUSTE_POSITIVO", "AJUSTE_NEGATIVO"])
@pytest.mark.parametrize("motivo", [None, "", "   "])
def test_ajustes_exigen_motivo(bodega, tipo, motivo):
    verificar_422(error_de(bodega, tipo, "1", "10.0000", motivo=motivo), "motivo")


def test_ajuste_negativo_como_una_salida(bodega):
    aplicar(bodega, "ENTRADA_COMPRA", "10", "20.0000")
    movimiento = aplicar(bodega, "AJUSTE_NEGATIVO", "4", "1.0000")["movimiento"]
    assert (movimiento["saldo_resultante"], movimiento["costo_promedio"]) == (D("6"), D("20"))
    assert movimiento["costo_unitario"] == D("20.0000")


def test_devolucion_cliente_al_costo_vigente(bodega):
    aplicar(bodega, "ENTRADA_COMPRA", "10", "30.0000")
    movimiento = aplicar(bodega, "DEVOLUCION_CLIENTE", "2", "99.0000")["movimiento"]
    assert movimiento["costo_unitario"] == D("30.0000")
    assert movimiento["costo_promedio"] == D("30.0000")
    assert movimiento["saldo_resultante"] == D("12")


def test_devolucion_cliente_sin_costo_previo_queda_en_cero(bodega):
    # Limitación conocida (D20): sin costo vigente la devolución entra a 0.
    movimiento = aplicar(bodega, "DEVOLUCION_CLIENTE", "2")["movimiento"]
    assert movimiento["costo_promedio"] == 0 and movimiento["valor_resultante"] == 0


def test_devolucion_proveedor_como_una_salida(bodega):
    aplicar(bodega, "ENTRADA_COMPRA", "10", "30.0000")
    movimiento = aplicar(bodega, "DEVOLUCION_PROVEEDOR", "10")["movimiento"]
    assert movimiento["saldo_resultante"] == 0
    assert movimiento["costo_promedio"] == D("30.0000")


def test_traslado_salida_y_entrada(bodega):
    destino = crear_bodega("B2")
    aplicar(bodega, "ENTRADA_COMPRA", "10", "40.0000")
    aplicar(destino, "ENTRADA_COMPRA", "10", "20.0000")
    salida = aplicar(bodega, "TRASLADO_SALIDA", "5")["movimiento"]
    entrada = aplicar(destino, "TRASLADO_ENTRADA", "5", salida["costo_unitario"])["movimiento"]
    assert salida["saldo_resultante"] == D("5")
    assert entrada["costo_unitario"] == D("40.0000")
    assert entrada["costo_promedio"] == D("26.6667")  # (10*20 + 5*40) / 15


def test_traslado_entrada_exige_costo(bodega):
    verificar_422(error_de(bodega, "TRASLADO_ENTRADA", "1"), "costo_unitario")


# --- Validaciones -------------------------------------------------------------------


@pytest.mark.parametrize("cantidad", ["0", "-1", "1.0001", "100000000000"])
def test_cantidad_invalida(bodega, cantidad):
    verificar_422(error_de(bodega, "ENTRADA_COMPRA", cantidad, "1.0000"), "cantidad")


def test_unidad_solo_enteros(bodega):
    verificar_422(error_de(bodega, "ENTRADA_COMPRA", "1.5", "1.0000", unidad="UNIDAD"), "cantidad")
    assert aplicar(bodega, "ENTRADA_COMPRA", "2.000", "1.0000", unidad="UNIDAD")["movimiento"]


@pytest.mark.parametrize("unidad", ["KILO", "LITRO"])
def test_kilo_y_litro_con_tres_decimales(bodega, unidad):
    assert aplicar(bodega, "ENTRADA_COMPRA", "1.125", "1.0000", unidad=unidad)["movimiento"][
        "saldo_resultante"] == D("1.125")


@pytest.mark.parametrize("costo", ["-0.0001", "1.00001", "10000000000"])
def test_costo_invalido(bodega, costo):
    verificar_422(error_de(bodega, "ENTRADA_COMPRA", "1", costo), "costo_unitario")


def test_saldo_resultante_mayor_que_el_maximo(bodega):
    aplicar(bodega, "ENTRADA_COMPRA", "99999999999.999", "0.0001")
    verificar_422(error_de(bodega, "ENTRADA_COMPRA", "0.001", "0.0001"), "cantidad")
    assert len(kardex(bodega)) == 1


def test_valor_resultante_mayor_que_el_maximo(bodega):
    verificar_422(error_de(bodega, "ENTRADA_COMPRA", "99999999999", "9999999999.0000"), "cantidad")
    assert saldo(bodega) is None


def test_varios_errores_juntos(bodega):
    error = error_de(bodega, "AJUSTE_POSITIVO", "-1", "-5", motivo="")
    verificar_422(error, "cantidad", "costo_unitario", "motivo")


def test_entrada_compra_sin_costo(bodega):
    verificar_422(error_de(bodega, "ENTRADA_COMPRA", "1"), "costo_unitario")


def test_tipo_desconocido_lanza_value_error(bodega):
    with pytest.raises(ValueError):
        aplicar(bodega, "REGALO", "1", "1.0000")


def test_cantidad_float_lanza_value_error(bodega):
    with transaccion(CONFIG) as cur, pytest.raises(ValueError):
        aplicar_movimiento(cur, sku=SKU, id_bodega=bodega, tipo="SALIDA", cantidad=1.5,
                           id_usuario=7, unidad_medida="KILO", stock_minimo=D("0"))


# --- Bodega ---------------------------------------------------------------------------


def test_bodega_inexistente_da_404():
    error = error_de(999_999_999, "ENTRADA_COMPRA", "1", "1.0000")
    assert (error.status, error.codigo, error.mensaje) == (404, "NO_EXISTE", "La bodega no existe.")


def test_bodega_inactiva_da_422_y_no_escribe():
    inactiva = crear_bodega("INA", estado="INACTIVO")
    verificar_422(error_de(inactiva, "ENTRADA_COMPRA", "1", "1.0000"), "id_bodega")
    assert saldo(inactiva) is None and kardex(inactiva) == []


# --- Stock mínimo y umbral --------------------------------------------------------------


def test_saldo_guarda_la_copia_fresca_del_minimo(bodega):
    aplicar(bodega, "ENTRADA_COMPRA", "10", "1.0000", minimo="2")
    assert saldo(bodega)["stock_minimo"] == D("2")
    aplicar(bodega, "SALIDA", "1", minimo="4.5")
    assert saldo(bodega)["stock_minimo"] == D("4.5")


@pytest.mark.parametrize(
    "inicial, tipo, cantidad, minimo, esperado",
    [
        ("10", "SALIDA", "8", "5", True),              # de arriba a abajo
        ("10", "SALIDA", "5", "5", True),              # termina exactamente en el mínimo
        ("4", "SALIDA", "1", "5", False),              # ya estaba abajo
        ("4", "ENTRADA_COMPRA", "3", "5", False),      # sube por encima
        ("2", "ENTRADA_COMPRA", "1", "5", False),      # sigue abajo
        ("5", "SALIDA", "1", "5", False),              # empezó igual, no mayor
        ("3", "SALIDA", "3", "0", True),               # mínimo 0 y llega a 0
    ],
)
def test_cruce_del_umbral(bodega, inicial, tipo, cantidad, minimo, esperado):
    aplicar(bodega, "ENTRADA_COMPRA", inicial, "1.0000", minimo=minimo)
    resultado = aplicar(bodega, tipo, cantidad, "1.0000", minimo=minimo)
    assert resultado["cruzo_umbral"] is esperado
    assert resultado["saldo_anterior"] == D(inicial)
    assert resultado["stock_minimo"] == D(minimo)


# --- Fila del kardex -----------------------------------------------------------------


def test_fila_del_kardex(bodega):
    traslado_destino = crear_bodega("B2")
    with transaccion(CONFIG) as cur:
        cur.execute(
            "INSERT INTO traslados (sku, id_bodega_origen, id_bodega_destino, cantidad, id_usuario)"
            " VALUES (%s, %s, %s, %s, %s)", (SKU, bodega, traslado_destino, D("1"), 7))
        id_traslado = cur.lastrowid
    aplicar(bodega, "ENTRADA_COMPRA", "3.5", "12.3456", documento_referencia="OC-15")
    resultado = aplicar(bodega, "TRASLADO_SALIDA", "1", motivo="Reposición",
                        documento_referencia=f"TR-{id_traslado}", id_traslado=id_traslado)

    movimiento = resultado["movimiento"]
    assert set(movimiento) == CAMPOS_MOVIMIENTO
    fila = kardex(bodega)[-1]
    for campo in CAMPOS_MOVIMIENTO - {"fecha"}:
        assert fila[campo] == movimiento[campo], campo
    assert fila["tipo"] == "TRASLADO_SALIDA"
    assert fila["saldo_resultante"] == D("2.5")
    assert fila["costo_promedio"] == D("12.3456")
    assert fila["valor_resultante"] == D("30.86")  # 2.5 * 12.3456 = 30.864
    assert fila["id_usuario"] == 7
    assert fila["motivo"] == "Reposición"
    assert fila["documento_referencia"] == f"TR-{id_traslado}"
    assert fila["id_traslado"] == id_traslado
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs(ahora - fila["fecha"]) < timedelta(seconds=5)
    assert fila["fecha"] == movimiento["fecha"]


def test_actualizado_en_se_refresca(bodega):
    aplicar(bodega, "ENTRADA_COMPRA", "1", "1.0000")
    with transaccion(CONFIG) as cur:
        cur.execute(
            "UPDATE saldos SET actualizado_en = '2020-01-01 00:00:00' WHERE sku = %s AND id_bodega = %s",
            (SKU, bodega))
    assert saldo(bodega)["actualizado_en"].year == 2020
    aplicar(bodega, "ENTRADA_COMPRA", "1", "1.0000")
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs(ahora - saldo(bodega)["actualizado_en"]) < timedelta(seconds=5)


# --- Consistencia con GET /stock --------------------------------------------------------


def test_valor_resultante_coincide_con_el_round_de_mysql(bodega):
    azar = random.Random(7)
    actual = D("0")
    for _ in range(50):
        if actual > 0 and azar.random() < 0.4:
            cantidad = D(azar.randint(1, int(actual * 1000))) / 1000
            movimiento = aplicar(bodega, "SALIDA", str(cantidad))["movimiento"]
        else:
            cantidad = D(azar.randint(1, 100_000)) / 1000
            costo = D(azar.randint(0, 99_999_999)) / 10_000
            movimiento = aplicar(bodega, "ENTRADA_COMPRA", str(cantidad), str(costo))["movimiento"]
        actual = movimiento["saldo_resultante"]
        assert movimiento["valor_resultante"] == saldo(bodega)["valor"]
    verificar_cadena(kardex(bodega))


# --- Inmutabilidad del kardex ---------------------------------------------------------------


def test_la_app_no_modifica_ni_borra_movimientos():
    patron = re.compile(r"\b(UPDATE\s+`?movimientos`?|DELETE\s+FROM\s+`?movimientos`?)\b", re.I)
    raiz = Path(__file__).resolve().parent.parent / "app"
    archivos = list(raiz.rglob("*.py"))
    assert archivos
    culpables = [str(a) for a in archivos if patron.search(a.read_text(encoding="utf-8"))]
    assert culpables == []


# --- Concurrencia ----------------------------------------------------------------------------


def en_hilos(tareas):
    """Ejecuta las tareas a la vez y devuelve "ok" o el código de ApiError de cada una."""
    barrera = threading.Barrier(len(tareas))
    resultados = [None] * len(tareas)

    def correr(indice, tarea):
        barrera.wait()
        try:
            ejecutar_con_reintento(tarea)
            resultados[indice] = "ok"
        except ApiError as error:
            resultados[indice] = error.codigo
        except Exception as error:  # noqa: BLE001 - se reporta en la aserción
            resultados[indice] = f"inesperado: {error!r}"

    hilos = [threading.Thread(target=correr, args=(i, t)) for i, t in enumerate(tareas)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    return resultados


@pytest.mark.parametrize("ronda", range(5))
def test_concurrencia_salidas(bodega, ronda):
    aplicar(bodega, "ENTRADA_COMPRA", "10", "15.0000", unidad="UNIDAD")
    tareas = [lambda: aplicar(bodega, "SALIDA", "1", unidad="UNIDAD") for _ in range(20)]
    resultados = en_hilos(tareas)
    assert resultados.count("ok") == 10, resultados
    assert resultados.count("STOCK_INSUFICIENTE") == 10, resultados
    assert saldo(bodega)["cantidad"] == 0
    filas = kardex(bodega)
    assert len(filas) == 11  # la entrada inicial más 10 salidas
    assert verificar_cadena(filas) == 0


@pytest.mark.parametrize("ronda", range(5))
def test_concurrencia_entradas(bodega, ronda):
    tareas = [lambda: aplicar(bodega, "ENTRADA_COMPRA", "1", "10.0000") for _ in range(10)]
    tareas += [lambda: aplicar(bodega, "ENTRADA_COMPRA", "1", "20.0000") for _ in range(10)]
    resultados = en_hilos(tareas)
    assert resultados == ["ok"] * 20, resultados
    assert saldo(bodega)["cantidad"] == D("20")
    filas = kardex(bodega)
    assert len(filas) == 20
    assert verificar_cadena(filas) == D("20")


@pytest.mark.parametrize("ronda", range(5))
def test_concurrencia_mezclada(bodega, ronda):
    aplicar(bodega, "ENTRADA_COMPRA", "5", "10.0000")
    tareas = []
    for i in range(12):
        tareas.append(lambda: aplicar(bodega, "SALIDA", "2"))
        tareas.append(lambda i=i: aplicar(bodega, "ENTRADA_COMPRA", "1", f"{10 + i}.0000"))
    resultados = en_hilos(tareas)
    assert set(resultados) <= {"ok", "STOCK_INSUFICIENTE"}, resultados
    assert saldo(bodega)["cantidad"] >= 0
    verificar_cadena(kardex(bodega))
