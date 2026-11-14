"""Motor que aplica un movimiento a un saldo (D41).

Lo usan los movimientos manuales, los traslados, las devoluciones y los
consumidores de eventos. Recibe el cursor de una transacción que abre quien
llama, con el SKU canónico y el stock mínimo fresco de ms-productos (D39).
No publica eventos: solo devuelve los datos para publicarlos después del
commit (D8). Todos los cálculos se hacen con Decimal.
"""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.errors import ApiError
from app.repositorios import movimientos as repo_movimientos
from app.repositorios import saldos as repo_saldos
from app.validacion import Errores

ENTRADAS = frozenset({"ENTRADA_COMPRA", "AJUSTE_POSITIVO", "TRASLADO_ENTRADA", "DEVOLUCION_CLIENTE"})
SALIDAS = frozenset({"SALIDA", "AJUSTE_NEGATIVO", "TRASLADO_SALIDA", "DEVOLUCION_PROVEEDOR"})
CON_COSTO_OBLIGATORIO = frozenset({"ENTRADA_COMPRA", "TRASLADO_ENTRADA"})
AJUSTES = frozenset({"AJUSTE_POSITIVO", "AJUSTE_NEGATIVO"})
UNIDADES = frozenset({"UNIDAD", "KILO", "LITRO"})

MAX_CANTIDAD = Decimal("99999999999.999")      # DECIMAL(14,3)
MAX_COSTO = Decimal("9999999999.9999")         # DECIMAL(14,4)
MAX_VALOR = Decimal("9999999999999999.99")     # DECIMAL(18,2)
TRES_DECIMALES = Decimal("0.001")
CUATRO_DECIMALES = Decimal("0.0001")
DOS_DECIMALES = Decimal("0.01")
CERO = Decimal("0")
PRECISION = 40


def _decimales(valor):
    return max(0, -valor.as_tuple().exponent)


def valor_de(cantidad, costo):
    """cantidad * costo redondeado a 2 decimales, igual que ROUND de MySQL."""
    with localcontext() as contexto:
        contexto.prec = PRECISION
        return (cantidad * costo).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


def costo_ponderado(saldo, costo_vigente, cantidad, costo_entrada):
    """Costo promedio ponderado tras una entrada, a 4 decimales (ROUND_HALF_UP)."""
    with localcontext() as contexto:
        contexto.prec = PRECISION
        total = saldo * costo_vigente + cantidad * costo_entrada
        return (total / (saldo + cantidad)).quantize(CUATRO_DECIMALES, rounding=ROUND_HALF_UP)


def _validar_parametros(tipo, cantidad, unidad_medida, stock_minimo, costo_unitario, motivo):
    """Errores de programación (ValueError) y de datos (un solo 422)."""
    if tipo not in ENTRADAS and tipo not in SALIDAS:
        raise ValueError(f"Tipo de movimiento desconocido: {tipo}")
    if unidad_medida not in UNIDADES:
        raise ValueError(f"Unidad de medida desconocida: {unidad_medida}")
    for nombre, valor in (("cantidad", cantidad), ("stock_minimo", stock_minimo)):
        if not isinstance(valor, Decimal):
            raise ValueError(f"{nombre} debe ser Decimal")
    if costo_unitario is not None and not isinstance(costo_unitario, Decimal):
        raise ValueError("costo_unitario debe ser Decimal")

    errores = Errores()
    if not cantidad.is_finite() or cantidad <= 0:
        errores.agregar("cantidad", "Debe ser mayor que 0.")
    elif _decimales(cantidad) > 3:
        errores.agregar("cantidad", "Máximo 3 decimales.")
    elif cantidad > MAX_CANTIDAD:
        errores.agregar("cantidad", f"Debe ser menor o igual a {MAX_CANTIDAD}.")
    elif unidad_medida == "UNIDAD" and cantidad != cantidad.to_integral_value():
        errores.agregar("cantidad", "Con unidad_medida UNIDAD debe ser un número entero.")

    # El costo solo se valida donde se usa; en salidas y devoluciones de cliente se ignora.
    usa_costo = tipo in CON_COSTO_OBLIGATORIO or tipo == "AJUSTE_POSITIVO"
    if usa_costo and costo_unitario is None and tipo in CON_COSTO_OBLIGATORIO:
        errores.agregar("costo_unitario", "Es obligatorio para este tipo de movimiento.")
    elif usa_costo and costo_unitario is not None:
        if not costo_unitario.is_finite() or costo_unitario < 0:
            errores.agregar("costo_unitario", "Debe ser mayor o igual a 0.")
        elif _decimales(costo_unitario) > 4:
            errores.agregar("costo_unitario", "Máximo 4 decimales.")
        elif costo_unitario > MAX_COSTO:
            errores.agregar("costo_unitario", f"Debe ser menor o igual a {MAX_COSTO}.")

    if tipo in AJUSTES and not (isinstance(motivo, str) and motivo.strip()):
        errores.agregar("motivo", "Es obligatorio en los ajustes.")

    errores.lanzar_si_hay()


def _validar_bodega(cursor, id_bodega):
    bodega = repo_saldos.leer_bodega_compartida(cursor, id_bodega)
    if bodega is None:
        raise ApiError("NO_EXISTE", "La bodega no existe.", 404)
    if bodega["estado"] != "ACTIVO":
        raise ApiError(
            "VALIDACION", "Revisa los campos enviados.", 422,
            {"id_bodega": ["La bodega está inactiva."]},
        )


def aplicar_movimiento(cursor, *, sku, id_bodega, tipo, cantidad, id_usuario, unidad_medida,
                       stock_minimo, costo_unitario=None, motivo=None,
                       documento_referencia=None, id_traslado=None):
    """Aplica el movimiento y devuelve {movimiento, saldo_anterior, stock_minimo, cruzo_umbral}."""
    # 1. Parámetros
    _validar_parametros(tipo, cantidad, unidad_medida, stock_minimo, costo_unitario, motivo)
    es_entrada = tipo in ENTRADAS

    # 2. Bodega existente y activa (D6)
    _validar_bodega(cursor, id_bodega)

    # 3. Saldo bloqueado. Una salida no crea el saldo: si no existe, cuenta como 0.
    if es_entrada:
        repo_saldos.asegurar_saldo(cursor, sku, id_bodega, stock_minimo)
    saldo = repo_saldos.bloquear_saldo(cursor, sku, id_bodega)
    saldo_anterior = saldo["cantidad"] if saldo else CERO
    costo_vigente = saldo["costo_promedio"] if saldo else CERO

    # 4. Cálculo
    if es_entrada:
        if tipo == "DEVOLUCION_CLIENTE":
            costo_entrada = costo_vigente  # D20
        elif costo_unitario is not None:
            costo_entrada = costo_unitario
        elif saldo_anterior == 0:
            # AJUSTE_POSITIVO sin costo y sin saldo: no hay costo vigente que usar (D10).
            raise ApiError(
                "VALIDACION", "Revisa los campos enviados.", 422,
                {"costo_unitario": ["Es obligatorio cuando el saldo es 0."]},
            )
        else:
            costo_entrada = costo_vigente
        saldo_resultante = saldo_anterior + cantidad
        costo_resultante = costo_ponderado(saldo_anterior, costo_vigente, cantidad, costo_entrada)
        costo_movimiento = costo_entrada
    else:
        saldo_resultante = saldo_anterior - cantidad
        if saldo_resultante < 0:
            raise ApiError(
                "STOCK_INSUFICIENTE",
                "No hay saldo suficiente para esta salida.",
                409,
                {"cantidad": [f"Saldo disponible: {saldo_anterior}."]},
            )
        costo_resultante = costo_vigente  # una salida no cambia el costo (D10)
        costo_movimiento = costo_vigente

    if saldo_resultante > MAX_CANTIDAD:
        raise ApiError(
            "VALIDACION", "Revisa los campos enviados.", 422,
            {"cantidad": [f"El saldo resultante superaría el máximo de {MAX_CANTIDAD}."]},
        )
    valor_resultante = valor_de(saldo_resultante, costo_resultante)
    if valor_resultante > MAX_VALOR:
        raise ApiError(
            "VALIDACION", "Revisa los campos enviados.", 422,
            {"cantidad": ["El valor del saldo resultante superaría el máximo permitido."]},
        )

    movimiento = {
        "sku": sku,
        "id_bodega": id_bodega,
        "tipo": tipo,
        "cantidad": cantidad.quantize(TRES_DECIMALES),
        "costo_unitario": costo_movimiento.quantize(CUATRO_DECIMALES),
        "saldo_resultante": saldo_resultante.quantize(TRES_DECIMALES),
        "costo_promedio": costo_resultante,
        "valor_resultante": valor_resultante,
        "motivo": motivo,
        "documento_referencia": documento_referencia,
        "id_usuario": id_usuario,
        "id_traslado": id_traslado,
    }

    # 5. Fila del kardex (fecha fijada ya con el saldo bloqueado)
    id_movimiento, fecha = repo_movimientos.insertar_movimiento(cursor, **movimiento)

    # 6. Saldo nuevo, con la copia fresca del stock mínimo (D1)
    repo_saldos.actualizar_saldo(
        cursor, saldo["id_saldo"], movimiento["saldo_resultante"], costo_resultante, stock_minimo
    )

    return {
        "movimiento": {"id_movimiento": id_movimiento, **movimiento, "fecha": fecha},
        "saldo_anterior": saldo_anterior,
        "stock_minimo": stock_minimo,
        # D7: solo al cruzar el umbral de arriba hacia abajo
        "cruzo_umbral": saldo_anterior > stock_minimo and saldo_resultante <= stock_minimo,
    }
