from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render
from django.views import View

from apps.equipos.models import CategoriaEquipo
from apps.ubicaciones.models import Ambiente

from .exports import exportar_excel, exportar_pdf
from .services import DEFINICIONES_REPORTES, generar_reporte


class ReportesView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "cuentas.ver_reportes"
    raise_exception = True

    def get(self, request):
        clave = request.GET.get("reporte", DEFINICIONES_REPORTES[0][0])
        reporte = generar_reporte(clave, request.user, request.GET)
        formato = request.GET.get("formato", "")
        if formato:
            if not request.user.has_perm("cuentas.exportar_reportes"):
                from django.core.exceptions import PermissionDenied

                raise PermissionDenied
            if formato == "excel":
                return exportar_excel(reporte)
            if formato == "pdf":
                return exportar_pdf(reporte, request.GET)
        return render(request, "reportes/lista.html", {
            "reporte": reporte,
            "reportes": DEFINICIONES_REPORTES,
            "ambientes": Ambiente.objects.filter(activo=True).order_by("bloque", "nombre"),
            "categorias": CategoriaEquipo.objects.filter(activo=True).order_by("nombre"),
            "puede_exportar": request.user.has_perm("cuentas.exportar_reportes"),
            "filtros": request.GET,
        })