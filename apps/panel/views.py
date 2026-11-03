from django.db.models import Count, Q
from django.utils import timezone
from django.views.generic import TemplateView

from apps.equipos.models import Equipo
from apps.preventivo.models import MantenimientoProgramado
from apps.solicitudes.models import Solicitud


class PanelInicioView(TemplateView):
    template_name = "panel/inicio.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        puede_ver = usuario.is_authenticated and (usuario.is_superuser or usuario.has_perm("cuentas.ver_dashboard"))
        context["mostrar_indicadores"] = puede_ver
        if not puede_ver:
            return context

        equipos = Equipo.objects.values("estado").annotate(total=Count("pk"))
        context["equipos_por_estado"] = [
            {"estado": Equipo.Estado(item["estado"]).label, "valor": item["total"]}
            for item in equipos
        ]
        context["total_equipos"] = sum(item["valor"] for item in context["equipos_por_estado"])

        solicitudes_abiertas = Solicitud.objects.filter(
            estado__in=[Solicitud.Estado.REGISTRADA, Solicitud.Estado.ASIGNADA, Solicitud.Estado.EN_REPARACION]
        )
        context["solicitudes_por_prioridad"] = [
            {"prioridad": prioridad.label, "valor": solicitudes_abiertas.filter(prioridad=prioridad.value).count()}
            for prioridad in Solicitud.Prioridad
        ]
        context["total_solicitudes_abiertas"] = solicitudes_abiertas.count()
        context["preventivos_vencidos"] = MantenimientoProgramado.objects.filter(
            estado=MantenimientoProgramado.Estado.PENDIENTE,
            fecha_programada__lt=timezone.localdate(),
        ).count()
        context["preventivos_proximos"] = MantenimientoProgramado.objects.filter(
            estado=MantenimientoProgramado.Estado.PENDIENTE,
            fecha_programada__gte=timezone.localdate(),
        ).order_by("fecha_programada").select_related("equipo", "plan")[:5]
        if usuario.has_perm("cuentas.ver_solicitudes"):
            ultimas = Solicitud.objects.select_related("equipo", "solicitante").order_by("-fecha_reporte")
            if not (usuario.is_superuser or usuario.has_perm("cuentas.ver_todas_solicitudes")):
                ultimas = ultimas.filter(Q(solicitante=usuario) | Q(tecnico_asignado=usuario))
            context["ultimas_solicitudes"] = ultimas[:6]
        else:
            context["ultimas_solicitudes"] = []
        if not usuario.has_perm("cuentas.ver_preventivos"):
            context["preventivos_proximos"] = []
        return context