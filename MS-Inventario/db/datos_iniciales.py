"""Datos iniciales de ms-inventario: bodegas y una semana de operación (D51).

Uso, desde la carpeta del servicio:

    python -m db.datos_iniciales

Solo siembra si la base no tiene bodegas, así que correrlo de nuevo (o reiniciar
el contenedor) no duplica nada. Todos los saldos nacen de movimientos aplicados
con aplicar_movimiento, en una sola transacción y sin publicar eventos. Los
movimientos quedan con la fecha del sembrado.
"""

import sys
from decimal import Decimal

from app.config import cargar_configuracion
from app.db import transaccion
from app.errors import ApiError
from app.repositorios import traslados as repo_traslados
from app.servicios.movimientos import aplicar_movimiento

ID_USUARIO = 1
MOTIVO_INICIAL = "inventario inicial"

BODEGAS = [
    ("BOD-PRINCIPAL", "Bodega principal", "Calle 13 # 68-50, Bogotá"),
    ("BOD-SALA", "Sala de ventas", "Carrera 7 # 45-20, Bogotá"),
    ("BOD-NORTE", "Bodega norte", "Autopista Norte # 170-30, Bogotá"),
]

# Copia de los productos de ms-productos (los servicios son independientes):
# sku: (unidad_medida, stock_minimo, costo unitario de compra)
PRODUCTOS = {
    "LAC-0001": ("UNIDAD", "24", "3450.0000"),
    "LAC-0002": ("UNIDAD", "24", "3950.0000"),
    "LAC-0003": ("LITRO", "20.500", "2900.0000"),
    "LAC-0004": ("UNIDAD", "10", "9100.0000"),
    "LAC-0005": ("KILO", "4.500", "20500.0000"),
    "LAC-0006": ("UNIDAD", "12", "6900.0000"),
    "BEB-0001": ("UNIDAD", "30", "4600.0000"),
    "BEB-0002": ("UNIDAD", "30", "3300.0000"),
    "BEB-0003": ("UNIDAD", "20", "2950.0000"),
    "BEB-0004": ("UNIDAD", "15", "3650.0000"),
    "BEB-0005": ("UNIDAD", "48", "1100.0000"),
    "BEB-0006": ("UNIDAD", "24", "1300.0000"),
    "GRA-0001": ("UNIDAD", "40", "3300.0000"),
    "GRA-0002": ("UNIDAD", "10", "15800.0000"),
    "GRA-0003": ("UNIDAD", "15", "5600.0000"),
    "GRA-0004": ("KILO", "8.500", "4700.0000"),
    "GRA-0005": ("UNIDAD", "12", "8500.0000"),
    "GRA-0006": ("UNIDAD", "6", "23900.0000"),
    "ASE-0001": ("UNIDAD", "10", "17200.0000"),
    "ASE-0002": ("UNIDAD", "8", "20100.0000"),
    "ASE-0003": ("UNIDAD", "30", "2200.0000"),
    "ASE-0004": ("UNIDAD", "20", "2700.0000"),
    "ASE-0005": ("LITRO", "6.000", "5300.0000"),
    "PAN-0001": ("UNIDAD", "15", "5600.0000"),
    "PAN-0002": ("UNIDAD", "50", "350.0000"),
    "PAN-0003": ("UNIDAD", "10", "3100.0000"),
    "CAR-0001": ("KILO", "5.000", "19800.0000"),
    "CAR-0002": ("KILO", "3.500", "32400.0000"),
    "CAR-0003": ("KILO", "6.000", "13900.0000"),
    "CAR-0004": ("KILO", "8.000", "9300.0000"),
    "FRU-0001": ("KILO", "10.000", "2100.0000"),
    "FRU-0002": ("KILO", "20.000", "1800.0000"),
    "FRU-0003": ("KILO", "8.500", "3000.0000"),
}

# Bodega norte: solo productos no perecederos
NORTE = ("BEB-", "GRA-", "ASE-")

# Ventas de la semana en la sala: (sku, cantidad, documento)
VENTAS = [
    ("LAC-0001", "5", "POS-000101"),
    ("BEB-0003", "4", "POS-000102"),
    ("GRA-0001", "6", "POS-000103"),
    ("ASE-0003", "5", "POS-000104"),
    ("FRU-0001", "2.500", "POS-000105"),
    ("CAR-0001", "1.250", "POS-000106"),
    ("LAC-0005", "0.750", "POS-000107"),
]

# Reposición de la sala: (sku, origen, destino, cantidad)
TRASLADOS = [
    ("LAC-0001", "BOD-PRINCIPAL", "BOD-SALA", "24"),
    ("GRA-0001", "BOD-NORTE", "BOD-SALA", "20"),
]

# Devolución de un cliente en la sala: (sku, cantidad, factura, motivo)
DEVOLUCION = ("LAC-0004", "1", "POS-000110", "Cliente devolvió el producto sin abrir")

# Ventas grandes del fin de semana que dejan dos productos bajo el mínimo en la sala
VENTAS_FIN_DE_SEMANA = [
    ("BEB-0001", "35", "POS-000121"),
    ("PAN-0001", "18", "POS-000122"),
]


def base_vacia(cursor):
    cursor.execute("SELECT COUNT(*) AS n FROM bodegas")
    return cursor.fetchone()["n"] == 0


def insertar(cursor, prefijo_bodega="", prefijo_sku=""):
    """Crea las bodegas y aplica los movimientos de la semana.

    Si alguna de las bodegas ya existe, no hace nada (devuelve 0 movimientos).
    Los prefijos solo los usan las pruebas, para no chocar con los datos reales.
    Devuelve el número de movimientos aplicados.
    """
    codigos = [prefijo_bodega + codigo for codigo, _, _ in BODEGAS]
    marcadores = ", ".join(["%s"] * len(codigos))
    cursor.execute(f"SELECT COUNT(*) AS n FROM bodegas WHERE codigo IN ({marcadores})", codigos)
    if cursor.fetchone()["n"]:
        return 0

    ids = {}
    for codigo, nombre, direccion in BODEGAS:
        cursor.execute("INSERT INTO bodegas (codigo, nombre, direccion) VALUES (%s, %s, %s)",
                       (prefijo_bodega + codigo, nombre, direccion))
        ids[codigo] = cursor.lastrowid

    aplicados = 0

    def mover(sku, bodega, tipo, cantidad, **extra):
        nonlocal aplicados
        unidad, minimo, _ = PRODUCTOS[sku]
        resultado = aplicar_movimiento(
            cursor, sku=prefijo_sku + sku, id_bodega=ids[bodega], tipo=tipo,
            cantidad=Decimal(cantidad), id_usuario=ID_USUARIO, unidad_medida=unidad,
            stock_minimo=Decimal(minimo), **extra)
        aplicados += 1
        return resultado

    # 1. Inventario inicial al costo de compra
    for sku, (_, minimo, costo) in PRODUCTOS.items():
        minimo = Decimal(minimo)
        cantidades = {"BOD-PRINCIPAL": minimo * 6, "BOD-SALA": minimo * 2}
        if sku.startswith(NORTE):
            cantidades["BOD-NORTE"] = minimo * 3
        for bodega, cantidad in cantidades.items():
            mover(sku, bodega, "AJUSTE_POSITIVO", cantidad, costo_unitario=Decimal(costo),
                  motivo=MOTIVO_INICIAL)

    # 2. Ventas de la semana
    for sku, cantidad, documento in VENTAS:
        mover(sku, "BOD-SALA", "SALIDA", cantidad, motivo="Venta", documento_referencia=documento)

    # 3. Traslados de reposición (los dos movimientos con el mismo documento)
    for sku, origen, destino, cantidad in TRASLADOS:
        motivo = "Reposición de la sala de ventas"
        id_traslado = repo_traslados.insertar(
            cursor, prefijo_sku + sku, ids[origen], ids[destino], Decimal(cantidad), motivo, ID_USUARIO)
        comunes = {"motivo": motivo, "documento_referencia": f"TR-{id_traslado}", "id_traslado": id_traslado}
        salida = mover(sku, origen, "TRASLADO_SALIDA", cantidad, **comunes)
        mover(sku, destino, "TRASLADO_ENTRADA", cantidad,
              costo_unitario=salida["movimiento"]["costo_promedio"], **comunes)

    # 4. Devolución de un cliente
    sku, cantidad, factura, motivo = DEVOLUCION
    mover(sku, "BOD-SALA", "DEVOLUCION_CLIENTE", cantidad, motivo=motivo, documento_referencia=factura)

    # 5. Ventas que dejan productos bajo el mínimo
    for sku, cantidad, documento in VENTAS_FIN_DE_SEMANA:
        mover(sku, "BOD-SALA", "SALIDA", cantidad, motivo="Venta", documento_referencia=documento)

    return aplicados


def sembrar(config=None):
    """Siembra solo si no hay bodegas. Devuelve el número de movimientos (None si no sembró)."""
    config = config if config is not None else cargar_configuracion()
    with transaccion(config) as cursor:
        # Bloqueo de la tabla de registro: dos arranques simultáneos no siembran dos veces
        cursor.execute("SELECT nombre FROM migraciones_aplicadas FOR UPDATE")
        cursor.fetchall()
        if not base_vacia(cursor):
            return None
        return insertar(cursor)


def main():
    try:
        movimientos = sembrar()
    except ApiError as error:
        print(f"No se sembraron los datos iniciales: {error.mensaje}", file=sys.stderr)
        return 1
    if movimientos is None:
        print("La base ya tiene bodegas: no se siembran datos iniciales.")
    else:
        print(f"Datos iniciales: {len(BODEGAS)} bodegas y {movimientos} movimientos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
