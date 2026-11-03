from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from .forms import MantenimientoProgramadoForm, PlanPreventivoForm
from .models import MantenimientoProgramado, PlanPreventivo
from .services import completar_mantenimiento


class AccesoPreventivo(LoginRequiredMixin, PermissionRequiredMixin):
    raise_exception = True


class ListaProgramacionesView(AccesoPreventivo, ListView):
    model = MantenimientoProgramado
    template_name = "preventivo/programaciones.html"
    context_object_name = "programaciones"
    paginate_by = 30
    permission_required = "cuentas.ver_preventivos"

    def get_queryset(self):
        queryset = MantenimientoProgramado.objects.select_related("equipo", "equipo__ambiente", "equipo__categoria", "plan", "tecnico")
        estado, ambiente = self.request.GET.get("estado", ""), self.request.GET.get("ambiente", "")
        if estado:
            queryset = queryset.filter(estado=estado)
        if ambiente:
            queryset = queryset.filter(equipo__ambiente_id=ambiente)
        return queryset.order_by("fecha_programada", "equipo__codigo")

    def get_context_data(self, **kwargs):
        from apps.ubicaciones.models import Ambiente

        context = super().get_context_data(**kwargs)
        context.update({
            "estados": MantenimientoProgramado.Estado.choices,
            "ambientes": Ambiente.objects.filter(activo=True).order_by("bloque", "nombre"),
            "pendientes": MantenimientoProgramado.objects.filter(estado=MantenimientoProgramado.Estado.PENDIENTE).count(),
            "vencidos": MantenimientoProgramado.objects.filter(estado=MantenimientoProgramado.Estado.PENDIENTE, fecha_programada__lt=timezone.localdate()).count(),
        })
        return context


class ListaPlanesView(AccesoPreventivo, ListView):
    model = PlanPreventivo
    template_name = "preventivo/planes.html"
    context_object_name = "planes"
    permission_required = "cuentas.ver_preventivos"

    def get_queryset(self):
        return PlanPreventivo.objects.select_related("categoria").order_by("categoria__nombre", "nombre")


class CrearPlanView(AccesoPreventivo, CreateView):
    model = PlanPreventivo
    form_class = PlanPreventivoForm
    template_name = "preventivo/plan_formulario.html"
    permission_required = "cuentas.crear_preventivos"
    success_url = reverse_lazy("preventivo:planes")

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        messages.success(self.request, "El plan preventivo se creó correctamente.")
        return super().form_valid(form)


class EditarPlanView(AccesoPreventivo, UpdateView):
    model = PlanPreventivo
    form_class = PlanPreventivoForm
    template_name = "preventivo/plan_formulario.html"
    permission_required = "cuentas.editar_preventivos"
    success_url = reverse_lazy("preventivo:planes")

    def form_valid(self, form):
        messages.success(self.request, "El plan preventivo se actualizó correctamente.")
        return super().form_valid(form)


class CrearProgramacionView(AccesoPreventivo, CreateView):
    model = MantenimientoProgramado
    form_class = MantenimientoProgramadoForm
    template_name = "preventivo/programacion_formulario.html"
    permission_required = "cuentas.crear_preventivos"
    success_url = reverse_lazy("preventivo:programaciones")

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        messages.success(self.request, "El mantenimiento se programó correctamente.")
        return super().form_valid(form)


class CompletarProgramacionView(AccesoPreventivo, View):
    permission_required = "cuentas.editar_preventivos"

    def get(self, request, pk):
        mantenimiento = get_object_or_404(MantenimientoProgramado.objects.select_related("equipo", "plan"), pk=pk)
        return render(request, "preventivo/confirmar_realizado.html", {"mantenimiento": mantenimiento})

    def post(self, request, pk):
        mantenimiento = get_object_or_404(MantenimientoProgramado, pk=pk)
        _, siguiente = completar_mantenimiento(mantenimiento, request.user)
        if siguiente:
            messages.success(request, f"Mantenimiento realizado. El siguiente quedó programado para {siguiente.fecha_programada:%d/%m/%Y}.")
        else:
            messages.info(request, "Este mantenimiento ya estaba completado.")
        return redirect("preventivo:programaciones")


class CancelarProgramacionView(AccesoPreventivo, View):
    permission_required = "cuentas.editar_preventivos"

    def post(self, request, pk):
        mantenimiento = get_object_or_404(MantenimientoProgramado, pk=pk, estado=MantenimientoProgramado.Estado.PENDIENTE)
        mantenimiento.estado = MantenimientoProgramado.Estado.CANCELADO
        mantenimiento.actualizado_por = request.user
        mantenimiento.save(update_fields=["estado", "actualizado_por", "actualizado_en"])
        messages.success(request, "La programación se canceló y permanece en el historial.")
        return redirect("preventivo:programaciones")