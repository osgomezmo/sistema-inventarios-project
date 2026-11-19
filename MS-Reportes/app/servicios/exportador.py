"""Servicio para exportación de reportes a formatos CSV y PDF."""

import csv
from datetime import datetime, timezone
from decimal import Decimal
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _formatear_celda(valor):
    if valor is None:
        return ""
    if isinstance(valor, (Decimal, float)):
        return f"{float(valor):,.2f}"
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    return str(valor)


def exportar_csv(titulo, encabezados, filas, filtros=None):
    """Genera un archivo CSV codificado en UTF-8."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    if filtros:
        writer.writerow([f"# Reporte: {titulo}"])
        writer.writerow([f"# Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}"])
        for k, v in filtros.items():
            if v is not None:
                writer.writerow([f"# Filtro {k}: {v}"])

    writer.writerow(encabezados)

    for fila in filas:
        writer.writerow([_formatear_celda(celda) for celda in fila])

    return output.getvalue().encode("utf-8")


def exportar_pdf(titulo, encabezados, filas, filtros=None):
    """Genera un archivo PDF binario usando reportlab."""
    buffer = io.BytesIO()

    orientacion = landscape(letter) if len(encabezados) > 5 else letter
    doc = SimpleDocTemplate(
        buffer,
        pagesize=orientacion,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    titulo_style = styles["Heading1"]
    subtitulo_style = styles["Normal"]

    elementos = []

    elementos.append(Paragraph(f"<b>{titulo}</b>", titulo_style))
    fecha_gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    elementos.append(Paragraph(f"Fecha de generación (UTC): {fecha_gen}", subtitulo_style))

    if filtros:
        filtros_txt = " | ".join(f"<b>{k}:</b> {v}" for k, v in filtros.items() if v is not None)
        if filtros_txt:
            elementos.append(Spacer(1, 6))
            elementos.append(Paragraph(f"Filtros aplicados: {filtros_txt}", subtitulo_style))

    elementos.append(Spacer(1, 14))

    datos_tabla = [encabezados]
    for fila in filas:
        datos_tabla.append([_formatear_celda(celda) for celda in fila])

    if len(datos_tabla) == 1:
        datos_tabla.append(["Sin registros para mostrar"] + [""] * (len(encabezados) - 1))

    tabla = Table(datos_tabla, repeatRows=1)
    tabla.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9F9")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
        ])
    )

    elementos.append(tabla)
    doc.build(elementos)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
