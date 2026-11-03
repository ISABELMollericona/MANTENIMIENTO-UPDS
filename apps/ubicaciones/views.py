from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from .forms import AmbienteForm
from .models import Ambiente


class AccesoUbicaciones(LoginRequiredMixin, PermissionRequiredMixin):
    raise_exception = True


class ListaAmbientesView(AccesoUbicaciones, ListView):
    model = Ambiente
    template_name = "ubicaciones/lista.html"
    context_object_name = "ambientes"
    paginate_by = 20
    permission_required = "cuentas.ver_ambientes"

    def get_queryset(self):
        queryset = Ambiente.objects.select_related("responsable")
        busqueda = self.request.GET.get("q", "").strip()
        tipo = self.request.GET.get("tipo", "")
        bloque = self.request.GET.get("bloque", "").strip()
        estado = self.request.GET.get("estado", "activo")
        if busqueda:
            queryset = queryset.filter(nombre__icontains=busqueda) | queryset.filter(bloque__icontains=busqueda)
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        if bloque:
            queryset = queryset.filter(bloque__icontains=bloque)
        if estado in {"activo", "inactivo"}:
            queryset = queryset.filter(activo=(estado == "activo"))
        return queryset.order_by("bloque", "nombre")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tipos"] = Ambiente.Tipo.choices
        return context


class CrearAmbienteView(AccesoUbicaciones, CreateView):
    model = Ambiente
    form_class = AmbienteForm
    template_name = "ubicaciones/formulario.html"
    permission_required = "cuentas.crear_ambientes"
    success_url = reverse_lazy("ubicaciones:lista")

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        messages.success(self.request, "El ambiente se registró correctamente.")
        return super().form_valid(form)


class EditarAmbienteView(AccesoUbicaciones, UpdateView):
    model = Ambiente
    form_class = AmbienteForm
    template_name = "ubicaciones/formulario.html"
    permission_required = "cuentas.editar_ambientes"
    success_url = reverse_lazy("ubicaciones:lista")

    def form_valid(self, form):
        messages.success(self.request, "El ambiente se actualizó correctamente.")
        return super().form_valid(form)


class DesactivarAmbienteView(AccesoUbicaciones, View):
    permission_required = "cuentas.dar_baja_ambientes"

    def get(self, request, pk):
        from django.shortcuts import render

        ambiente = get_object_or_404(Ambiente, pk=pk, activo=True)
        return render(request, "ubicaciones/confirmar_baja.html", {"ambiente": ambiente})

    def post(self, request, pk):
        ambiente = get_object_or_404(Ambiente, pk=pk, activo=True)
        ambiente.activo = False
        ambiente.save(update_fields=["activo", "actualizado_en"])
        messages.success(request, "El ambiente se desactivó sin borrar su historial.")
        return redirect("ubicaciones:lista")