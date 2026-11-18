"""Controladores y rutas para los 4 endpoints de la Tabla 10:

- GET /reportes/valorizacion
- GET /reportes/rotacion
- GET /reportes/stock-bajo
- GET /dashboard
"""

from decimal import Decimal
from flask import Blueprint, Response, jsonify, request

from app.clientes.productos_client import obtener_catalogo_productos
from app.db import transaccion
from app.paginacion import leer_paginacion
from app.repositorios import reportes_repo as repo
from app.servicios.exportador import exportar_csv, exportar_pdf
from app.validacion import Errores, entero_opcional, fecha_opcional, opcion

reportes_bp = Blueprint("reportes_routes", __name__)

AGRUPACIONES_VALIDAS = ("producto", "categoria", "bodega")
FORMATOS_VALIDOS = ("json", "csv", "pdf")


@reportes_bp.get("/reportes/valorizacion")
def reporte_valorizacion():
    errores = Errores()
    agrupar = opcion(errores, request.args, "agrupar", AGRUPACIONES_VALIDAS) or "producto"
    id_bodega = entero_opcional(errores, request.args, "id_bodega", minimo=1)
    formato = opcion(errores, request.args, "formato", FORMATOS_VALIDOS) or "json"
    errores.lanzar_si_hay()

    with transaccion() as cursor:
        totales = repo.obtener_totales_valorizacion(cursor, id_bodega=id_bodega)

        if agrupar == "categoria":
            # Requiere obligatoriamente catálogo de productos (503 si falla)
            catalogo = obtener_catalogo_productos(requerido=True)
            saldos = repo.obtener_valorizacion_por_producto(cursor, id_bodega=id_bodega)

            agrupado = {}
            for fila in saldos:
                sku = fila["sku"]
                info = catalogo.get(sku, {})
                categoria = info.get("categoria_nombre", "Sin categoría")
                id_cat = info.get("id_categoria", 0)

                if categoria not in agrupado:
                    agrupado[categoria] = {
                        "categoria": categoria,
                        "id_categoria": id_cat,
                        "cantidad_total": Decimal("0.000"),
                        "valor_total": Decimal("0.00"),
                        "total_productos": 0,
                    }
                agrupado[categoria]["cantidad_total"] += Decimal(str(fila["cantidad"]))
                agrupado[categoria]["valor_total"] += Decimal(str(fila["valor_total"]))
                agrupado[categoria]["total_productos"] += 1

            datos = []
            for item in sorted(agrupado.values(), key=lambda x: x["valor_total"], reverse=True):
                cant = item["cantidad_total"]
                val = item["valor_total"]
                costo_prom = float(val / cant) if cant > 0 else 0.0
                datos.append({
                    "clave": str(item["id_categoria"] or item["categoria"]),
                    "nombre": item["categoria"],
                    "categoria": item["categoria"],
                    "id_categoria": item["id_categoria"],
                    "total_productos": item["total_productos"],
                    "cantidad": float(cant),
                    "cantidad_total": float(cant),
                    "costo_promedio": costo_prom,
                    "valor": float(val),
                    "valor_total": float(val),
                })

            encabezados = ["Categoría", "Total Productos", "Cantidad Total", "Costo Promedio", "Valor Total"]
            filas_exportar = [
                [d["categoria"], d["total_productos"], d["cantidad_total"], d["costo_promedio"], d["valor_total"]]
                for d in datos
            ]

        elif agrupar == "bodega":
            filas = repo.obtener_valorizacion_por_bodega(cursor, id_bodega=id_bodega)
            datos = [
                {
                    "clave": str(fila["id_bodega"]),
                    "nombre": f"Bodega {fila['id_bodega']}",
                    "id_bodega": fila["id_bodega"],
                    "total_productos": fila["total_productos"],
                    "cantidad": float(fila["cantidad_total"]),
                    "cantidad_total": float(fila["cantidad_total"]),
                    "valor": float(fila["valor_total"]),
                    "valor_total": float(fila["valor_total"]),
                }
                for fila in filas
            ]
            encabezados = ["Bodega", "Total Productos", "Cantidad Total", "Valor Total"]
            filas_exportar = [
                [d["id_bodega"], d["total_productos"], d["cantidad_total"], d["valor_total"]]
                for d in datos
            ]

        else:  # agrupar == "producto"
            catalogo = obtener_catalogo_productos(requerido=False)
            filas = repo.obtener_valorizacion_por_producto(cursor, id_bodega=id_bodega)
            datos = []
            for fila in filas:
                sku = fila["sku"]
                info = catalogo.get(sku, {})
                datos.append({
                    "clave": f"{sku}-{fila['id_bodega']}",
                    "sku": sku,
                    "nombre": info.get("nombre", sku),
                    "categoria": info.get("categoria_nombre", "Sin categoría"),
                    "id_bodega": fila["id_bodega"],
                    "cantidad": float(fila["cantidad"]),
                    "costo_promedio": float(fila["costo_promedio"]),
                    "valor": float(fila["valor_total"]),
                    "valor_total": float(fila["valor_total"]),
                    "actualizado_en": fila["actualizado_en"],
                })
            encabezados = ["SKU", "Nombre", "Categoría", "Bodega", "Cantidad", "Costo Promedio", "Valor Total"]
            filas_exportar = [
                [d["sku"], d["nombre"], d["categoria"], d["id_bodega"], d["cantidad"], d["costo_promedio"], d["valor_total"]]
                for d in datos
            ]

    filtros = {"agrupar": agrupar, "id_bodega": id_bodega}

    if formato == "csv":
        csv_bytes = exportar_csv("Reporte de Valorización", encabezados, filas_exportar, filtros=filtros)
        return Response(
            csv_bytes,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="reporte_valorizacion.csv"'},
        )

    if formato == "pdf":
        pdf_bytes = exportar_pdf("Reporte de Valorización", encabezados, filas_exportar, filtros=filtros)
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="reporte_valorizacion.pdf"'},
        )

    # JSON paginado
    page, per_page, offset = leer_paginacion()
    total_registros = len(datos)
    datos_paginados = datos[offset : offset + per_page]

    return jsonify({
        "data": datos_paginados,
        "resumen": {
            "cantidad_total": float(totales["cantidad_total"]),
            "valor_total": float(totales["valor_total"]),
        },
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total_registros,
        },
    })


@reportes_bp.get("/reportes/rotacion")
def reporte_rotacion():
    errores = Errores()
    desde = fecha_opcional(errores, request.args, "desde")
    hasta = fecha_opcional(errores, request.args, "hasta")
    id_bodega = entero_opcional(errores, request.args, "id_bodega", minimo=1)
    top = entero_opcional(errores, request.args, "top", minimo=1) or 10
    formato = opcion(errores, request.args, "formato", FORMATOS_VALIDOS) or "json"

    if desde and hasta and desde > hasta:
        errores.agregar("desde", "La fecha 'desde' no puede ser posterior a 'hasta'.")
    errores.lanzar_si_hay()

    with transaccion() as cursor:
        filas = repo.obtener_rotacion(cursor, desde=desde, hasta=hasta, id_bodega=id_bodega)

    catalogo = obtener_catalogo_productos(requerido=False)

    lista_productos = []
    for f in filas:
        sku = f["sku"]
        info = catalogo.get(sku, {})
        salidas = float(f["total_salidas"])
        lista_productos.append({
            "sku": sku,
            "nombre": info.get("nombre", sku),
            "categoria": info.get("categoria_nombre", "Sin categoría"),
            "total_entradas": float(f["total_entradas"]),
            "total_salidas": salidas,
            "unidades_salida": salidas,
            "rotacion": salidas,
        })

    mayor_rotacion = sorted(
        lista_productos,
        key=lambda x: (x["total_salidas"], x["total_entradas"]),
        reverse=True,
    )[:top]

    menor_rotacion = sorted(
        lista_productos,
        key=lambda x: (x["total_salidas"], x["total_entradas"]),
    )[:top]

    filtros = {"desde": desde, "hasta": hasta, "id_bodega": id_bodega, "top": top}

    if formato in ("csv", "pdf"):
        encabezados = ["Tipo Rotación", "SKU", "Nombre", "Categoría", "Entradas", "Salidas"]
        filas_exportar = []
        for p in mayor_rotacion:
            filas_exportar.append(["Mayor", p["sku"], p["nombre"], p["categoria"], p["total_entradas"], p["total_salidas"]])
        for p in menor_rotacion:
            filas_exportar.append(["Menor", p["sku"], p["nombre"], p["categoria"], p["total_entradas"], p["total_salidas"]])

        if formato == "csv":
            csv_bytes = exportar_csv("Reporte de Rotación", encabezados, filas_exportar, filtros=filtros)
            return Response(
                csv_bytes,
                mimetype="text/csv; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="reporte_rotacion.csv"'},
            )

        pdf_bytes = exportar_pdf("Reporte de Rotación", encabezados, filas_exportar, filtros=filtros)
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="reporte_rotacion.pdf"'},
        )

    return jsonify({
        "desde": desde,
        "hasta": hasta,
        "mayor_rotacion": mayor_rotacion,
        "menor_rotacion": menor_rotacion,
    })


@reportes_bp.get("/reportes/stock-bajo")
def reporte_stock_bajo():
    errores = Errores()
    id_bodega = entero_opcional(errores, request.args, "id_bodega", minimo=1)
    formato = opcion(errores, request.args, "formato", FORMATOS_VALIDOS) or "json"
    errores.lanzar_si_hay()

    with transaccion() as cursor:
        filas = repo.obtener_alertas_stock_bajo(cursor, id_bodega=id_bodega)

    catalogo = obtener_catalogo_productos(requerido=False)

    datos = []
    for f in filas:
        sku = f["sku"]
        info = catalogo.get(sku, {})
        datos.append({
            "sku": sku,
            "nombre": info.get("nombre", sku),
            "categoria": info.get("categoria_nombre", "Sin categoría"),
            "id_bodega": f["id_bodega"],
            "saldo": float(f["saldo"]),
            "stock_minimo": float(f["stock_minimo"]),
            "diferencia": float(f["diferencia"]),
            "fecha": f["fecha"],
            "activa": bool(f["activa"]),
        })

    filtros = {"id_bodega": id_bodega}
    encabezados = ["SKU", "Nombre", "Categoría", "Bodega", "Saldo Actual", "Stock Mínimo", "Déficit", "Fecha Alerta"]
    filas_exportar = [
        [d["sku"], d["nombre"], d["categoria"], d["id_bodega"], d["saldo"], d["stock_minimo"], d["diferencia"], d["fecha"]]
        for d in datos
    ]

    if formato == "csv":
        csv_bytes = exportar_csv("Reporte de Stock Bajo", encabezados, filas_exportar, filtros=filtros)
        return Response(
            csv_bytes,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="reporte_stock_bajo.csv"'},
        )

    if formato == "pdf":
        pdf_bytes = exportar_pdf("Reporte de Stock Bajo", encabezados, filas_exportar, filtros=filtros)
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="reporte_stock_bajo.pdf"'},
        )

    page, per_page, offset = leer_paginacion()
    total_registros = len(datos)
    datos_paginados = datos[offset : offset + per_page]

    return jsonify({
        "data": datos_paginados,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total_registros,
        },
    })


@reportes_bp.get("/dashboard")
def dashboard():
    errores = Errores()
    id_bodega = entero_opcional(errores, request.args, "id_bodega", minimo=1)
    errores.lanzar_si_hay()

    with transaccion() as cursor:
        if id_bodega is not None:
            metricas = repo.obtener_metricas_dashboard(cursor, id_bodega=id_bodega)
        else:
            metricas = repo.obtener_metricas_dashboard(cursor)

    catalogo = obtener_catalogo_productos(requerido=False)

    mayor_enriquecida = []
    for item in metricas["mayor_rotacion"]:
        sku = item["sku"]
        info = catalogo.get(sku, {})
        salidas = float(item["total_salidas"])
        mayor_enriquecida.append({
            "sku": sku,
            "nombre": info.get("nombre", sku),
            "categoria": info.get("categoria_nombre", "Sin categoría"),
            "total_entradas": float(item["total_entradas"]),
            "total_salidas": salidas,
            "unidades_salida": salidas,
            "rotacion": salidas,
        })

    menor_enriquecida = []
    for item in metricas["menor_rotacion"]:
        sku = item["sku"]
        info = catalogo.get(sku, {})
        salidas = float(item["total_salidas"])
        menor_enriquecida.append({
            "sku": sku,
            "nombre": info.get("nombre", sku),
            "categoria": info.get("categoria_nombre", "Sin categoría"),
            "total_entradas": float(item["total_entradas"]),
            "total_salidas": salidas,
            "unidades_salida": salidas,
            "rotacion": salidas,
        })

    return jsonify({
        "valor_total_inventario": metricas["valor_total_inventario"],
        "productos_stock_bajo": metricas["productos_stock_bajo"],
        "ordenes_pendientes": metricas["ordenes_pendientes"],
        "mayor_rotacion": mayor_enriquecida,
        "menor_rotacion": menor_enriquecida,
    })
