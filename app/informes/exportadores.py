"""Exportación CSV, Excel y PDF."""

import csv
import io
from typing import List

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def exportar_csv(filas: List[dict]) -> bytes:
    """Genera CSV en memoria (UTF-8 con BOM para Excel)."""
    buf = io.StringIO()
    buf.write("\ufeff")
    w = csv.writer(buf, delimiter=";")
    w.writerow(
        [
            "Código",
            "Empleado",
            "Horas trabajadas",
            "Normales",
            "Extras",
            "Nocturnas",
            "Festivas",
            "Nocturnas festivo",
            "Días incompletos",
        ]
    )
    for fila in filas:
        emp = fila["empleado"]
        r = fila["resumen"]
        w.writerow(
            [
                emp.codigo_empleado,
                emp.nombre_completo,
                r.get("horas_trabajadas", 0),
                r.get("horas_normales", 0),
                r.get("horas_extras", 0),
                r.get("horas_nocturnas", 0),
                r.get("horas_festivas", 0),
                r.get("horas_nocturnas_festivas", 0),
                r.get("dias_incompletos", 0),
            ]
        )
    return buf.getvalue().encode("utf-8")


def exportar_excel(filas: List[dict]) -> bytes:
    """Libro Excel simple con resumen."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Resumen"
    ws.append(
        [
            "Código",
            "Empleado",
            "Horas trab.",
            "Normales",
            "Extras",
            "Nocturnas",
            "Festivas",
        ]
    )
    for fila in filas:
        emp = fila["empleado"]
        r = fila["resumen"]
        ws.append(
            [
                emp.codigo_empleado,
                emp.nombre_completo,
                r.get("horas_trabajadas", 0),
                r.get("horas_normales", 0),
                r.get("horas_extras", 0),
                r.get("horas_nocturnas", 0),
                r.get("horas_festivas", 0),
            ]
        )
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def exportar_pdf(filas: List[dict], titulo: str, periodo: str) -> bytes:
    """PDF sencillo con tabla de resumen."""
    bio = io.BytesIO()
    doc = SimpleDocTemplate(bio, pagesize=A4, title=titulo)
    estilos = getSampleStyleSheet()
    elems = [
        Paragraph(titulo, estilos["Title"]),
        Paragraph(f"Periodo: {periodo}", estilos["Normal"]),
        Spacer(1, 12),
    ]
    datos = [
        [
            "Código",
            "Empleado",
            "H.trab.",
            "Norm.",
            "Ext.",
            "Noc.",
        ]
    ]
    for fila in filas:
        emp = fila["empleado"]
        r = fila["resumen"]
        datos.append(
            [
                emp.codigo_empleado,
                emp.nombre_completo[:28],
                f"{r.get('horas_trabajadas', 0):.2f}",
                f"{r.get('horas_normales', 0):.2f}",
                f"{r.get('horas_extras', 0):.2f}",
                f"{r.get('horas_nocturnas', 0):.2f}",
            ]
        )
    tabla = Table(datos, repeatRows=1)
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d1b2a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
            ]
        )
    )
    elems.append(tabla)
    doc.build(elems)
    return bio.getvalue()
