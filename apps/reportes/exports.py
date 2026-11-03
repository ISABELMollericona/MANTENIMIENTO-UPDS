from io import BytesIO

from django.http import HttpResponse
from django.template.loader import render_to_string
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from xhtml2pdf import pisa


def exportar_excel(reporte):
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Reporte"
    hoja.append(reporte["headers"])
    for celda in hoja[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="003A78")
    for fila in reporte["filas"]:
        hoja.append([fila.get(cabecera, "") for cabecera in reporte["headers"]])
    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = hoja.dimensions
    for columna in hoja.columns:
        ancho = max(len(str(celda.value or "")) for celda in columna)
        hoja.column_dimensions[columna[0].column_letter].width = min(ancho + 2, 45)
    archivo = BytesIO()
    libro.save(archivo)
    respuesta = HttpResponse(archivo.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    respuesta["Content-Disposition"] = f"attachment; filename={reporte['clave']}.xlsx"
    return respuesta


def exportar_pdf(reporte, filtros):
    html = render_to_string("reportes/pdf.html", {"reporte": reporte, "filtros": filtros})
    archivo = BytesIO()
    resultado = pisa.CreatePDF(html, dest=archivo, encoding="utf-8")
    if resultado.err:
        return HttpResponse("No se pudo generar el PDF.", status=500, content_type="text/plain; charset=utf-8")
    respuesta = HttpResponse(archivo.getvalue(), content_type="application/pdf")
    respuesta["Content-Disposition"] = f"attachment; filename={reporte['clave']}.pdf"
    return respuesta