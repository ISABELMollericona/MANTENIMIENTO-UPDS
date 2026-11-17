from datetime import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from apps.cuentas.models import Usuario

from .forms import AsignarTecnicoForm, CambiarEstadoSolicitudForm, SolicitudForm
from .models import Solicitud
from .services import TRANSICIONES_PERMITIDAS, asignar_tecnico, cambiar_estado


class AccesoSolicitudes(LoginRequiredMixin, PermissionRequiredMixin):
    @property
    def raise_exception(self):
        # Sin sesión: redirige al login (y vuelve aquí). Con sesión y sin permiso: 403.
        return self.request.user.is_authenticated


class ListaSolicitudesView(AccesoSolicitudes, ListView):
    model = Solicitud
    template_name = "solicitudes/lista.html"
    context_object_name = "solicitudes"
    paginate_by = 20
    permission_required = "cuentas.ver_solicitudes"

    def get_queryset(self):
        queryset = Solicitud.objects.select_related("equipo", "equipo__ambiente", "equipo__categoria", "equipo__equipo_principal", "solicitante", "tecnico_asignado")
        if not (self.request.user.is_superuser or self.request.user.has_perm("cuentas.ver_todas_solicitudes")):
            queryset = queryset.filter(Q(solicitante=self.request.user) | Q(tecnico_asignado=self.request.user))
        for campo in ("estado", "prioridad"):
            valor = self.request.GET.get(campo, "")
            if valor:
                queryset = queryset.filter(**{campo: valor})
        ambiente = self.request.GET.get("ambiente", "")
        tecnico = self.request.GET.get("tecnico", "")
        desde, hasta = self.request.GET.get("desde", ""), self.request.GET.get("hasta", "")
        if ambiente:
            queryset = queryset.filter(equipo__ambiente_id=ambiente)
        if tecnico:
            queryset = queryset.filter(tecnico_asignado_id=tecnico)
        if desde:
            try:
                queryset = queryset.filter(fecha_reporte__date__gte=datetime.strptime(desde, "%Y-%m-%d").date())
            except ValueError:
                pass
        if hasta:
            try:
                queryset = queryset.filter(fecha_reporte__date__lte=datetime.strptime(hasta, "%Y-%m-%d").date())
            except ValueError:
                pass
        consulta = self.request.GET.get("q", "").strip()
        if consulta:
            queryset = queryset.filter(Q(equipo__codigo__icontains=consulta) | Q(descripcion__icontains=consulta) | Q(docente_solicitante__icontains=consulta) | Q(solicitante__username__icontains=consulta))
        return queryset.order_by("-fecha_reporte", "-pk")

    def get_context_data(self, **kwargs):
        from apps.ubicaciones.models import Ambiente

        context = super().get_context_data(**kwargs)
        context.update({
            "estados": Solicitud.Estado.choices,
            "prioridades": Solicitud.Prioridad.choices,
            "ambientes": Ambiente.laboratorios(),
            "tecnicos": Usuario.objects.filter(is_active=True, solicitudes_asignadas__isnull=False).distinct().order_by("last_name", "first_name"),
            "puede_filtrar_tecnico": self.request.user.has_perm("cuentas.asignar_tecnico"),
        })
        return context


class CrearSolicitudView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Solicitud
    form_class = SolicitudForm
    template_name = "solicitudes/formulario.html"
    permission_required = "cuentas.crear_solicitudes"
    @property
    def raise_exception(self):
        # Sin sesión: redirige al login (y vuelve aquí). Con sesión y sin permiso: 403.
        return self.request.user.is_authenticated
    success_url = reverse_lazy("solicitudes:lista")

    def form_valid(self, form):
        form.instance.solicitante = self.request.user
        form.instance.creado_por = self.request.user
        messages.success(self.request, "El reporte de falla se registró correctamente.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("solicitudes:detalle", args=[self.object.pk])


class DetalleSolicitudView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Solicitud
    template_name = "solicitudes/detalle.html"
    context_object_name = "solicitud"
    permission_required = "cuentas.ver_solicitudes"
    @property
    def raise_exception(self):
        # Sin sesión: redirige al login (y vuelve aquí). Con sesión y sin permiso: 403.
        return self.request.user.is_authenticated

    def get_queryset(self):
        queryset = Solicitud.objects.select_related("equipo", "equipo__ambiente", "equipo__categoria", "equipo__equipo_principal", "solicitante", "tecnico_asignado").prefetch_related("historial__usuario")
        if not (self.request.user.is_superuser or self.request.user.has_perm("cuentas.ver_todas_solicitudes")):
            queryset = queryset.filter(Q(solicitante=self.request.user) | Q(tecnico_asignado=self.request.user))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["puede_cambiar_estado"] = self.request.user.has_perm("cuentas.cambiar_estado_solicitud") or (
            self.object.solicitante_id == self.request.user.pk and self.request.user.has_perm("cuentas.cancelar_solicitudes")
        )
        context["puede_asignar"] = self.request.user.has_perm("cuentas.asignar_tecnico")
        context["asignacion_form"] = AsignarTecnicoForm()
        # Solo se ofrecen los cambios que esta persona puede hacer desde el estado actual.
        usuario = self.request.user
        posibles = TRANSICIONES_PERMITIDAS.get(self.object.estado, set())
        reparacion_abierta = self.object.intervenciones.filter(fecha_devolucion__isnull=True).exists()
        opciones = []
        for valor, etiqueta in Solicitud.Estado.choices:
            if valor not in posibles or valor == Solicitud.Estado.ASIGNADA:
                continue  # La asignación se hace con el botón «Asignar», que exige elegir técnico.
            if valor == Solicitud.Estado.RESUELTA and reparacion_abierta:
                continue  # Se resuelve al registrar la devolución en la reparación.
            if valor == Solicitud.Estado.REGISTRADA and not usuario.has_perm("cuentas.reabrir_solicitud"):
                continue
            if not usuario.has_perm("cuentas.cambiar_estado_solicitud") and valor != Solicitud.Estado.CANCELADA:
                continue
            opciones.append((valor, "Reabrir (volver a registrada)" if valor == Solicitud.Estado.REGISTRADA else etiqueta))
        estado_form = CambiarEstadoSolicitudForm()
        estado_form.fields["estado"].choices = opciones
        context["estado_form"] = estado_form
        context["puede_cambiar_estado"] = context["puede_cambiar_estado"] and bool(opciones)
        if hasattr(self.object, "intervenciones"):
            context["intervenciones"] = self.object.intervenciones.select_related("tecnico", "laboratorio_origen")
            context["puede_editar_reparacion"] = self.request.user.has_perm("cuentas.editar_intervenciones")
        return context


class AsignarTecnicoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "cuentas.asignar_tecnico"
    @property
    def raise_exception(self):
        # Sin sesión: redirige al login (y vuelve aquí). Con sesión y sin permiso: 403.
        return self.request.user.is_authenticated

    def post(self, request, pk):
        solicitud = get_object_or_404(Solicitud, pk=pk)
        form = AsignarTecnicoForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Selecciona un técnico válido.")
            return redirect("solicitudes:detalle", pk=pk)
        try:
            asignar_tecnico(solicitud, form.cleaned_data["tecnico"], request.user)
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect("solicitudes:detalle", pk=pk)
        messages.success(request, "El técnico quedó asignado al reporte de falla.")
        return redirect("solicitudes:detalle", pk=pk)


class CambiarEstadoSolicitudView(LoginRequiredMixin, View):
    def post(self, request, pk):
        solicitud = get_object_or_404(Solicitud, pk=pk)
        form = CambiarEstadoSolicitudForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Revisa el estado y los datos requeridos.")
            return redirect("solicitudes:detalle", pk=pk)
        nuevo_estado = form.cleaned_data["estado"]
        cancelacion_propia = nuevo_estado == Solicitud.Estado.CANCELADA and solicitud.solicitante_id == request.user.pk and request.user.has_perm("cuentas.cancelar_solicitudes")
        reapertura = nuevo_estado == Solicitud.Estado.REGISTRADA and solicitud.estado in {Solicitud.Estado.RESUELTA, Solicitud.Estado.CANCELADA}
        if not cancelacion_propia and not request.user.has_perm("cuentas.cambiar_estado_solicitud"):
            raise PermissionDenied
        if reapertura and not (request.user.is_superuser or request.user.has_perm("cuentas.reabrir_solicitud")):
            raise PermissionDenied
        try:
            cambiar_estado(solicitud, nuevo_estado, request.user, comentario=form.cleaned_data["comentario"], motivo_cancelacion=form.cleaned_data["motivo_cancelacion"])
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect("solicitudes:detalle", pk=pk)
        messages.success(request, "El estado del reporte de falla se actualizó correctamente.")
        return redirect("solicitudes:detalle", pk=pk)