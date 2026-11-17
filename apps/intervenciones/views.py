from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.preventivo.models import MantenimientoPreventivo
from apps.solicitudes.models import Solicitud
from apps.solicitudes.services import cambiar_estado

from .forms import IntervencionForm
from .models import Intervencion


class AccesoIntervenciones(LoginRequiredMixin, PermissionRequiredMixin):
    @property
    def raise_exception(self):
        # Sin sesión: redirige al login (y vuelve aquí). Con sesión y sin permiso: 403.
        return self.request.user.is_authenticated


class MisTareasView(AccesoIntervenciones, ListView):
    """Lo que el técnico tiene asignado: reparaciones y mantenimientos preventivos."""

    model = Solicitud
    template_name = "intervenciones/mis_tareas.html"
    context_object_name = "solicitudes"
    paginate_by = 20
    permission_required = "cuentas.ver_intervenciones"

    def get_queryset(self):
        return (
            Solicitud.objects.filter(
                tecnico_asignado=self.request.user,
                estado__in=[Solicitud.Estado.ASIGNADA, Solicitud.Estado.EN_REPARACION],
            )
            .select_related("equipo", "equipo__ambiente", "equipo__categoria", "equipo__equipo_principal", "solicitante")
            .prefetch_related("intervenciones")
            .order_by(
                Case(
                    When(prioridad=Solicitud.Prioridad.ALTA, then=Value(0)),
                    When(prioridad=Solicitud.Prioridad.MEDIA, then=Value(1)),
                    default=Value(2),
                    output_field=IntegerField(),
                ),
                "fecha_reporte",
                "pk",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["preventivos"] = (
            MantenimientoPreventivo.objects.filter(tecnico=self.request.user, estado=MantenimientoPreventivo.Estado.PENDIENTE)
            .select_related("laboratorio")
            .order_by("fecha_programada")
        )
        context["puede_marcar_preventivo"] = self.request.user.has_perm("cuentas.editar_preventivos")
        return context


def _guardar_reparacion(request, form, solicitud):
    """Guarda la reparación y avanza el reporte de falla (en reparación / resuelto)."""
    with transaction.atomic():
        reparacion = form.save(commit=False)
        if not reparacion.pk:
            reparacion.solicitud = solicitud
            reparacion.tecnico = request.user
            reparacion.creado_por = request.user
            reparacion.laboratorio_origen = solicitud.equipo.ambiente
        reparacion.full_clean()
        reparacion.save()
        if solicitud.estado == Solicitud.Estado.ASIGNADA:
            solicitud = cambiar_estado(solicitud, Solicitud.Estado.EN_REPARACION, request.user, f"Salida a reparación el {reparacion.fecha_salida:%d/%m/%Y}.")
        if reparacion.fecha_devolucion:
            solicitud = cambiar_estado(
                solicitud,
                Solicitud.Estado.RESUELTA,
                request.user,
                comentario=f"Devuelto el {reparacion.fecha_devolucion:%d/%m/%Y}: {reparacion.get_resultado_display()}.",
                no_reparable=reparacion.resultado == Intervencion.Resultado.NO_REPARABLE,
            )
    return reparacion, solicitud


class CrearIntervencionView(AccesoIntervenciones, View):
    """El técnico asignado registra la salida del equipo a reparación."""

    permission_required = "cuentas.crear_intervenciones"

    def get_solicitud(self, request, solicitud_id):
        solicitud = get_object_or_404(
            Solicitud.objects.select_related("equipo", "equipo__ambiente", "tecnico_asignado"),
            pk=solicitud_id,
        )
        if solicitud.tecnico_asignado_id != request.user.pk:
            raise PermissionDenied("Solo el técnico asignado puede registrar la reparación.")
        if solicitud.estado != Solicitud.Estado.ASIGNADA:
            abierta = solicitud.intervenciones.filter(fecha_devolucion__isnull=True, tecnico=request.user).first()
            if abierta:
                return redirect("intervenciones:editar", pk=abierta.pk)
            raise Http404("El reporte no está disponible para registrar una reparación.")
        return solicitud

    def _render(self, request, form, solicitud):
        return render(request, "intervenciones/formulario.html", {"form": form, "solicitud": solicitud, "reparacion": None})

    def get(self, request, solicitud_id):
        solicitud = self.get_solicitud(request, solicitud_id)
        if not isinstance(solicitud, Solicitud):
            return solicitud
        return self._render(request, IntervencionForm(solicitud=solicitud), solicitud)

    def post(self, request, solicitud_id):
        solicitud = self.get_solicitud(request, solicitud_id)
        if not isinstance(solicitud, Solicitud):
            return solicitud
        form = IntervencionForm(request.POST, solicitud=solicitud)
        if not form.is_valid():
            return self._render(request, form, solicitud)
        try:
            reparacion, solicitud = _guardar_reparacion(request, form, solicitud)
        except ValidationError as error:
            form.add_error(None, error)
            return self._render(request, form, solicitud)
        mensaje = "La reparación quedó registrada y el reporte se marcó como resuelto." if reparacion.terminada else "Se registró la salida del equipo a reparación."
        messages.success(request, mensaje)
        return redirect("solicitudes:detalle", pk=solicitud.pk)


class EditarIntervencionView(AccesoIntervenciones, View):
    """El técnico completa su reparación: trabajo realizado, repuestos y devolución."""

    permission_required = "cuentas.editar_intervenciones"

    def get_reparacion(self, request, pk):
        reparacion = get_object_or_404(Intervencion.objects.select_related("solicitud", "solicitud__equipo", "laboratorio_origen"), pk=pk)
        if reparacion.tecnico_id != request.user.pk or reparacion.solicitud.tecnico_asignado_id != request.user.pk:
            raise PermissionDenied("Solo el técnico asignado puede actualizar esta reparación.")
        if reparacion.terminada:
            raise Http404("Esta reparación ya está terminada.")
        return reparacion

    def _render(self, request, form, reparacion):
        return render(request, "intervenciones/formulario.html", {"form": form, "solicitud": reparacion.solicitud, "reparacion": reparacion})

    def get(self, request, pk):
        reparacion = self.get_reparacion(request, pk)
        return self._render(request, IntervencionForm(instance=reparacion, solicitud=reparacion.solicitud), reparacion)

    def post(self, request, pk):
        reparacion = self.get_reparacion(request, pk)
        form = IntervencionForm(request.POST, instance=reparacion, solicitud=reparacion.solicitud)
        if not form.is_valid():
            return self._render(request, form, reparacion)
        try:
            reparacion, solicitud = _guardar_reparacion(request, form, reparacion.solicitud)
        except ValidationError as error:
            form.add_error(None, error)
            return self._render(request, form, reparacion)
        messages.success(request, "Se registró la devolución y el reporte quedó resuelto." if reparacion.terminada else "La reparación se actualizó.")
        return redirect("solicitudes:detalle", pk=solicitud.pk)
