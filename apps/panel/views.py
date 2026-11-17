from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from apps.equipos.models import Equipo, EstadoEquipo
from apps.preventivo.models import MantenimientoPreventivo
from apps.solicitudes.models import Solicitud

# Clase CSS y color del gráfico según el comportamiento del estado.
ESTILO_POR_TIPO = {
    EstadoEquipo.Tipo.OPERATIVO: ("operativo", "#198754"),
    EstadoEquipo.Tipo.REPARACION: ("en_mantenimiento", "#e0a800"),
    EstadoEquipo.Tipo.BAJA: ("dado_de_baja", "#6c757d"),
}


@require_GET
def keepalive(request):
    response = HttpResponse(status=204)
    response["Cache-Control"] = "no-store"
    return response


def _accesos(usuario):
    """Atajos de la pantalla de inicio según lo que cada rol puede hacer."""
    accesos = []
    if usuario.has_perm("cuentas.crear_solicitudes"):
        accesos.append(("solicitudes:crear", "bi-exclamation-triangle", "Reportar una falla", "En nombre del docente que la informó."))
    if usuario.has_perm("cuentas.ver_intervenciones"):
        accesos.append(("intervenciones:mis_tareas", "bi-wrench-adjustable", "Mis tareas", "Reparaciones y mantenimientos que tienes asignados."))
    if usuario.has_perm("cuentas.ver_solicitudes"):
        accesos.append(("solicitudes:lista", "bi-clipboard-check", "Reportes de falla", "Seguimiento de los reportes."))
    if usuario.has_perm("cuentas.ver_equipos"):
        accesos.append(("equipos:lista", "bi-pc-display", "Estado de los equipos", "Consulta en qué estado está cada equipo."))
    if usuario.has_perm("cuentas.ver_preventivos"):
        accesos.append(("preventivo:cronograma", "bi-calendar2-check", "Cronograma preventivo", "Mantenimientos programados del año."))
    return accesos


class PanelInicioView(TemplateView):
    template_name = "panel/inicio.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        puede_ver = usuario.is_authenticated and (usuario.is_superuser or usuario.has_perm("cuentas.ver_dashboard"))
        context["mostrar_indicadores"] = puede_ver
        if usuario.is_authenticated and not puede_ver:
            context["accesos"] = _accesos(usuario)
        if not puede_ver:
            return context

        conteos = dict(Equipo.objects.values_list("estado").annotate(total=Count("pk")))
        context["equipos_por_estado"] = []
        for estado in EstadoEquipo.objects.filter(Q(activo=True) | Q(pk__in=conteos.keys())):
            clave, color = ESTILO_POR_TIPO[estado.tipo]
            context["equipos_por_estado"].append({"clave": clave, "tipo": estado.tipo, "estado": estado.nombre, "etiqueta": estado.nombre.replace("/", "/​"), "valor": conteos.get(estado.pk, 0), "color": color, "id": estado.pk})
        context["total_equipos"] = sum(item["valor"] for item in context["equipos_por_estado"])

        solicitudes_abiertas = Solicitud.objects.filter(
            estado__in=[Solicitud.Estado.REGISTRADA, Solicitud.Estado.ASIGNADA, Solicitud.Estado.EN_REPARACION]
        )
        context["solicitudes_por_prioridad"] = [
            {"prioridad": prioridad.label, "valor": solicitudes_abiertas.filter(prioridad=prioridad.value).count()}
            for prioridad in Solicitud.Prioridad
        ]
        context["total_solicitudes_abiertas"] = solicitudes_abiertas.count()
        context["sin_asignar"] = solicitudes_abiertas.filter(estado=Solicitud.Estado.REGISTRADA).count()
        hoy = timezone.localdate()
        pendientes = MantenimientoPreventivo.objects.filter(estado=MantenimientoPreventivo.Estado.PENDIENTE)
        context["preventivos_vencidos"] = pendientes.filter(fecha_programada__lt=hoy).count()
        context["preventivos_proximos"] = pendientes.filter(fecha_programada__gte=hoy).order_by("fecha_programada").select_related("laboratorio", "tecnico")[:5]
        context["bajas_sin_informar"] = Equipo.objects.filter(estado__tipo=EstadoEquipo.Tipo.BAJA, informado_vicerrectoria=False).count()
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
