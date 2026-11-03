from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from apps.solicitudes.models import Solicitud
from apps.solicitudes.services import cambiar_estado

from .forms import IntervencionForm, RepuestoUsadoFormSet
from .models import Intervencion


class AccesoIntervenciones(LoginRequiredMixin, PermissionRequiredMixin):
    raise_exception = True


class MisTareasView(AccesoIntervenciones, ListView):
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
            .select_related("equipo", "equipo__ambiente", "equipo__categoria", "solicitante")
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


class CrearIntervencionView(AccesoIntervenciones, View):
    permission_required = "cuentas.crear_intervenciones"

    def get_solicitud(self, request, solicitud_id):
        solicitud = get_object_or_404(
            Solicitud.objects.select_related("equipo", "equipo__ambiente", "tecnico_asignado"),
            pk=solicitud_id,
        )
        if solicitud.tecnico_asignado_id != request.user.pk:
            raise PermissionDenied("Solo el técnico asignado puede registrar intervenciones.")
        if solicitud.estado not in {Solicitud.Estado.ASIGNADA, Solicitud.Estado.EN_REPARACION}:
            raise Http404("La solicitud no está disponible para intervención.")
        return solicitud

    def get(self, request, solicitud_id):
        solicitud = self.get_solicitud(request, solicitud_id)
        return render(request, "intervenciones/formulario.html", {
            "form": IntervencionForm(),
            "formset": RepuestoUsadoFormSet(prefix="repuestos"),
            "solicitud": solicitud,
        })

    def post(self, request, solicitud_id):
        solicitud = self.get_solicitud(request, solicitud_id)
        form = IntervencionForm(request.POST)
        formset = RepuestoUsadoFormSet(request.POST, prefix="repuestos")
        if not (form.is_valid() and formset.is_valid()):
            return render(request, "intervenciones/formulario.html", {"form": form, "formset": formset, "solicitud": solicitud})
        try:
            with transaction.atomic():
                intervencion = form.save(commit=False)
                intervencion.solicitud = solicitud
                intervencion.tecnico = request.user
                intervencion.creado_por = request.user
                intervencion.full_clean()
                intervencion.save()
                formset.instance = intervencion
                formset.save()
                if solicitud.estado == Solicitud.Estado.ASIGNADA:
                    solicitud = cambiar_estado(solicitud, Solicitud.Estado.EN_REPARACION, request.user, "Intervención iniciada.")
                if intervencion.fecha_fin:
                    solicitud = cambiar_estado(
                        solicitud,
                        Solicitud.Estado.RESUELTA,
                        request.user,
                        comentario=f"Intervención finalizada: {intervencion.get_resultado_display()}.",
                        no_reparable=intervencion.resultado == Intervencion.Resultado.NO_REPARABLE,
                    )
        except ValidationError as error:
            form.add_error(None, error)
            return render(request, "intervenciones/formulario.html", {"form": form, "formset": formset, "solicitud": solicitud})
        messages.success(request, "La intervención se registró correctamente.")
        return redirect("solicitudes:detalle", pk=solicitud.pk)