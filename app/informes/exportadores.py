"""Exportación CSV, Excel y PDF."""

import csv
import io
from datetime import date, timedelta
from typing import List

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


_TITULO_PDF_OFICIAL = "Informe de registro de jornada laboral"
_TITULO_PDF_INDIVIDUAL = "Informe mensual individual"


def _escape_xml(texto: str) -> str:
    """
    Escapa solo el texto variable para ReportLab Paragraph (mini-HTML).
    Las etiquetas <b> deben ir sin escapar; si se escapa todo, se ven literalmente.
    """
    if texto is None:
        return ""
    return (
        str(texto)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def exportar_csv(filas: List[dict]) -> bytes:
    """Genera CSV en memoria (UTF-8 con BOM para Excel)."""
    buf = io.StringIO()
    buf.write("\ufeff")
    w = csv.writer(buf, delimiter=";")
    w.writerow(
        [
            "Tipo día",
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
                fila.get("resumen_tipos_dia") or "—",
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
            "Tipo día",
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
                fila.get("resumen_tipos_dia") or "—",
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


def exportar_pdf(
    filas: List[dict],
    titulo: str,
    periodo: str,
    *,
    fecha_emision: date | None = None,
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
) -> bytes:
    """
    PDF con formato de registro de jornada (art. 34.9 ET), encabezado de empresa y pie legal.
    Un solo empleado con fechas: tabla diaria (informe mensual individual).
    """
    from app.empleados.calendario_servicios import (
        mapa_clasificaciones_manual_rango,
        resolver_estado_dia_laboral,
    )
    from app.fichajes.calculos import clasificar_dia, obtener_registros_dia
    from app.informes.servicios import etiqueta_estado_dia_laboral
    from app.utilidades.fechas import formatear_fecha

    es_pdf_individual_diario = (
        len(filas) == 1
        and fecha_inicio is not None
        and fecha_fin is not None
    )
    titulo_metadatos = (
        _TITULO_PDF_INDIVIDUAL if es_pdf_individual_diario else (titulo or _TITULO_PDF_OFICIAL)
    )
    bio = io.BytesIO()
    doc = SimpleDocTemplate(
        bio,
        pagesize=A4,
        title=titulo_metadatos,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=14 * mm,
        bottomMargin=18 * mm,
    )
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        name="TituloCentrado",
        parent=estilos["Title"],
        alignment=TA_CENTER,
        spaceAfter=18,
        spaceBefore=0,
    )
    estilo_encabezado = ParagraphStyle(
        name="EncabezadoEmpresa",
        parent=estilos["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=4,
    )
    estilo_encabezado_der = ParagraphStyle(
        name="EncabezadoTrabajadorDer",
        parent=estilos["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=4,
        alignment=TA_RIGHT,
    )
    estilo_periodo = ParagraphStyle(
        name="Periodo",
        parent=estilos["Normal"],
        fontSize=10,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    estilo_legal = ParagraphStyle(
        name="Legal",
        parent=estilos["Normal"],
        fontSize=8,
        leading=11,
        alignment=TA_JUSTIFY,
        spaceBefore=8,
        spaceAfter=10,
    )
    estilo_firma = ParagraphStyle(
        name="Firmas",
        parent=estilos["Normal"],
        fontSize=10,
        leading=16,
        spaceAfter=4,
    )
    estilo_firma_empresa = ParagraphStyle(
        name="FirmaEmpresa",
        parent=estilo_firma,
        alignment=TA_LEFT,
    )
    estilo_firma_trabajador = ParagraphStyle(
        name="FirmaTrabajador",
        parent=estilo_firma,
        alignment=TA_RIGHT,
    )

    elems: list = []

    # —— Encabezado: empresa (razón social, CIF, centro trabajo) ——
    empresa_nombre = "—"
    empresa_cif = "—"
    centro_txt = "—"
    if filas:
        emp0 = filas[0]["empleado"]
        ent = getattr(emp0, "empresa", None)
        if ent is not None:
            empresa_nombre = ent.nombre or "—"
            empresa_cif = ent.cif or "—"
        ids_emp = {f["empleado"].empresa_id for f in filas}
        if len(ids_emp) > 1:
            empresa_nombre = "Varias empresas (informe consolidado)"
            empresa_cif = "—"
        centros = {f["empleado"].centro_trabajo or "" for f in filas}
        centros.discard("")
        if len(centros) == 1:
            centro_txt = next(iter(centros))
        elif len(centros) > 1:
            centro_txt = "Varios centros de trabajo"
        else:
            centro_txt = emp0.centro_trabajo or "—"

    ancho_util = A4[0] - doc.leftMargin - doc.rightMargin

    if len(filas) == 1:
        emp = filas[0]["empleado"]
        nif = (emp.documento_identidad or "").strip() or "—"
        datos_encabezado = [
            [
                Paragraph(
                    f"<b>Empresa (razón social):</b> {_escape_xml(empresa_nombre)}",
                    estilo_encabezado,
                ),
                Paragraph(
                    f"<b>Nombre completo:</b> {_escape_xml(emp.nombre_completo)}",
                    estilo_encabezado_der,
                ),
            ],
            [
                Paragraph(
                    f"<b>CIF:</b> {_escape_xml(empresa_cif)}",
                    estilo_encabezado,
                ),
                Paragraph(
                    f"<b>NIF/DNI:</b> {_escape_xml(nif)}",
                    estilo_encabezado_der,
                ),
            ],
            [
                Paragraph(
                    f"<b>Centro de trabajo:</b> {_escape_xml(centro_txt)}",
                    estilo_encabezado,
                ),
                Paragraph(
                    f"<b>Código de empleado:</b> {_escape_xml(emp.codigo_empleado)}",
                    estilo_encabezado_der,
                ),
            ],
        ]
        tabla_enc = Table(
            datos_encabezado,
            colWidths=[ancho_util * 0.52, ancho_util * 0.48],
        )
        tabla_enc.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        elems.append(tabla_enc)
        elems.append(Spacer(1, 8))
    else:
        elems.append(
            Paragraph(
                f"<b>Empresa (razón social):</b> {_escape_xml(empresa_nombre)}",
                estilo_encabezado,
            )
        )
        elems.append(
            Paragraph(
                f"<b>CIF:</b> {_escape_xml(empresa_cif)}",
                estilo_encabezado,
            )
        )
        elems.append(
            Paragraph(
                f"<b>Centro de trabajo:</b> {_escape_xml(centro_txt)}",
                estilo_encabezado,
            )
        )
        elems.append(Spacer(1, 8))

    if len(filas) != 1 and filas:
        elems.append(
            Paragraph(
                "<b>Relación de trabajadores:</b> el detalle de cada persona "
                "figura en la tabla siguiente.",
                estilo_encabezado,
            )
        )
        elems.append(Spacer(1, 8))

    # —— Título oficial centrado ——
    elems.append(
        Paragraph(_escape_xml(titulo_metadatos), estilo_titulo)
    )
    elems.append(
        Paragraph(
            f"<b>Periodo:</b> {_escape_xml(periodo)}",
            estilo_periodo,
        )
    )

    # —— Tabla: un empleado + rango → una fila por día (informe mensual individual) ——
    estilo_th = ParagraphStyle(
        name="ThTablaPdf",
        parent=estilos["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=colors.whitesmoke,
    )
    estilo_td_tipo = ParagraphStyle(
        name="TdTipoDiaPdf",
        parent=estilos["Normal"],
        fontSize=7,
        leading=9,
    )
    ancho = A4[0] - 36 * mm
    fila_total_pdf: int | None = None

    if es_pdf_individual_diario:
        emp = filas[0]["empleado"]
        emp_id = emp.id
        manual_map = mapa_clasificaciones_manual_rango([emp_id], fecha_inicio, fecha_fin)
        datos = [
            [
                Paragraph("Fecha", estilo_th),
                Paragraph("Tipo<br/>día", estilo_th),
                Paragraph("Horas<br/>trabajadas", estilo_th),
                Paragraph("Horas<br/>ordinarias", estilo_th),
                Paragraph("Horas<br/>extraordinarias", estilo_th),
                Paragraph("Horas<br/>nocturnas", estilo_th),
            ]
        ]
        sum_trab = sum_norm = sum_extra = sum_noct = 0.0
        d = fecha_inicio
        while d <= fecha_fin:
            det = clasificar_dia(emp_id, d)
            regs = obtener_registros_dia(emp_id, d)
            cls = manual_map.get((emp_id, d))
            rlab = resolver_estado_dia_laboral(emp_id, d, manual=cls)
            estado = rlab["estado"]
            tipo_txt = etiqueta_estado_dia_laboral(estado)
            sin_datos_horas = len(regs) == 0 and estado == "pendiente"
            if sin_datos_horas:
                c_trab = c_norm = c_extra = c_noct = "sin datos"
            else:
                c_trab = f"{float(det.get('horas_trabajadas', 0)):.2f}"
                c_norm = f"{float(det.get('horas_normales', 0)):.2f}"
                c_extra = f"{float(det.get('horas_extras', 0)):.2f}"
                c_noct = f"{float(det.get('horas_nocturnas', 0)):.2f}"
                sum_trab += float(det.get("horas_trabajadas", 0))
                sum_norm += float(det.get("horas_normales", 0))
                sum_extra += float(det.get("horas_extras", 0))
                sum_noct += float(det.get("horas_nocturnas", 0))

            datos.append(
                [
                    formatear_fecha(d),
                    Paragraph(_escape_xml(tipo_txt), estilo_td_tipo),
                    c_trab,
                    c_norm,
                    c_extra,
                    c_noct,
                ]
            )
            d += timedelta(days=1)

        if len(datos) == 1:
            datos.append(
                [
                    "—",
                    Paragraph(_escape_xml("—"), estilo_td_tipo),
                    "sin datos",
                    "sin datos",
                    "sin datos",
                    "sin datos",
                ]
            )
        estilo_total = ParagraphStyle(
            name="TdTotalPdf",
            parent=estilos["Normal"],
            fontSize=8,
            fontName="Helvetica-Bold",
            leading=10,
        )
        datos.append(
            [
                Paragraph("<b>Total</b>", estilo_total),
                "",
                f"{sum_trab:.2f}",
                f"{sum_norm:.2f}",
                f"{sum_extra:.2f}",
                f"{sum_noct:.2f}",
            ]
        )
        fila_total_pdf = len(datos) - 1
        col_w = [
            ancho * 0.11,
            ancho * 0.26,
            ancho * 0.13,
            ancho * 0.13,
            ancho * 0.175,
            ancho * 0.175,
        ]
    else:
        datos = [
            [
                Paragraph("Tipo<br/>día", estilo_th),
                Paragraph("Empleado", estilo_th),
                Paragraph("Horas<br/>trabajadas", estilo_th),
                Paragraph("Horas<br/>ordinarias", estilo_th),
                Paragraph("Horas<br/>extraordinarias", estilo_th),
                Paragraph("Horas<br/>nocturnas", estilo_th),
            ]
        ]
        for fila in filas:
            emp = fila["empleado"]
            r = fila["resumen"]
            tipo_txt = fila.get("resumen_tipos_dia") or "—"
            datos.append(
                [
                    Paragraph(_escape_xml(tipo_txt), estilo_td_tipo),
                    emp.nombre_completo[:28],
                    f"{r.get('horas_trabajadas', 0):.2f}",
                    f"{r.get('horas_normales', 0):.2f}",
                    f"{r.get('horas_extras', 0):.2f}",
                    f"{r.get('horas_nocturnas', 0):.2f}",
                ]
            )
        if len(datos) == 1:
            datos.append(
                [
                    Paragraph(_escape_xml("—"), estilo_td_tipo),
                    "Sin datos en el periodo",
                    "0.00",
                    "0.00",
                    "0.00",
                    "0.00",
                ]
            )
        col_w = [
            ancho * 0.24,
            ancho * 0.20,
            ancho * 0.14,
            ancho * 0.14,
            ancho * 0.14,
            ancho * 0.14,
        ]

    tabla = Table(datos, colWidths=col_w, repeatRows=1)
    estilos_tabla = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d1b2a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        (
            "ROWBACKGROUNDS",
            (0, 1),
            (-1, -1),
            [colors.white, colors.HexColor("#f8f9fa")],
        ),
    ]
    if fila_total_pdf is not None:
        ft = fila_total_pdf
        estilos_tabla.extend(
            [
                ("LINEABOVE", (0, ft), (-1, ft), 0.75, colors.HexColor("#0d1b2a")),
                ("BACKGROUND", (0, ft), (-1, ft), colors.HexColor("#e9ecef")),
                ("SPAN", (0, ft), (1, ft)),
                ("FONTNAME", (0, ft), (-1, ft), "Helvetica-Bold"),
                ("ALIGN", (0, ft), (1, ft), "LEFT"),
            ]
        )
    tabla.setStyle(TableStyle(estilos_tabla))
    elems.append(tabla)
    elems.append(Spacer(1, 16))

    # —— Pie legal y firmas ——
    fe = fecha_emision or date.today()
    fecha_str = fe.strftime("%d/%m/%Y")
    texto_legal = (
        "El presente documento constituye un registro diario de la jornada laboral conforme "
        "a lo establecido en el artículo 34.9 del Estatuto de los Trabajadores. "
        "La empresa garantiza la veracidad de los datos reflejados."
    )
    elems.append(Paragraph(_escape_xml(texto_legal), estilo_legal))
    elems.append(Spacer(1, 6))
    ancho_firmas = A4[0] - 36 * mm
    mitad = ancho_firmas / 2
    tab_firmas = Table(
        [
            [
                Paragraph(
                    "Firma de la empresa: _______________________",
                    estilo_firma_empresa,
                ),
                Paragraph(
                    "Firma del trabajador/a: _______________________",
                    estilo_firma_trabajador,
                ),
            ]
        ],
        colWidths=[mitad, mitad],
    )
    tab_firmas.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elems.append(tab_firmas)
    elems.append(
        Paragraph(
            "Fecha de emisión: __ / __ / ____",
            estilo_firma,
        )
    )
    estilo_nota = ParagraphStyle(
        name="NotaPie",
        parent=estilos["Normal"],
        fontSize=7,
        textColor=colors.grey,
        spaceBefore=6,
    )
    elems.append(
        Paragraph(
            _escape_xml(f"Documento generado el {fecha_str}."),
            estilo_nota,
        )
    )

    doc.build(elems)
    return bio.getvalue()
