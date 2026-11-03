from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import CategoriaEquipoForm, EquipoForm
from .models import CategoriaEquipo, Equipo


class AccesoEquipos(LoginRequiredMixin, PermissionRequiredMixin):
    raise_exception = True


class ListaEquiposView(AccesoEquipos, ListView):
    model = Equipo
    template_name = "equipos/lista.html"
    context_object_name = "equipos"
    paginate_by = 20
    permission_required = "cuentas.ver_equipos"

    def get_queryset(self):
        queryset = Equipo.objects.select_related("categoria", "ambiente", "responsable")
        consulta = self.request.GET.get("q", "").strip()
        for campo in ("categoria", "ambiente", "estado"):
            valor = self.request.GET.get(campo, "")
            if valor:
                queryset = queryset.filter(**{f"{campo}_id" if campo != "estado" else campo: valor})
        if consulta:
            queryset = queryset.filter(
                Q(codigo__icontains=consulta)
                | Q(categoria__nombre__icontains=consulta)
                | Q(marca__icontains=consulta)
                | Q(modelo__icontains=consulta)
                | Q(numero_serie__icontains=consulta)
                | Q(ambiente__nombre__icontains=consulta)
            )
        return queryset.order_by("codigo")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categorias"] = CategoriaEquipo.objects.filter(activo=True)
        from apps.ubicaciones.models import Ambiente

        context["ambientes"] = Ambiente.objects.filter(activo=True).order_by("bloque", "nombre")
        context["estados"] = Equipo.Estado.choices
        return context


class CrearEquipoView(AccesoEquipos, CreateView):
    model = Equipo
    form_class = EquipoForm
    template_name = "equipos/formulario.html"
    permission_required = "cuentas.crear_equipos"
    success_url = reverse_lazy("equipos:lista")

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        form.instance._usuario_actualizacion = self.request.user
        messages.success(self.request, "El equipo se registró correctamente.")
        return super().form_valid(form)


class EditarEquipoView(AccesoEquipos, UpdateView):
    model = Equipo
    form_class = EquipoForm
    template_name = "equipos/formulario.html"
    permission_required = "cuentas.editar_equipos"
    success_url = reverse_lazy("equipos:lista")

    def form_valid(self, form):
        form.instance._usuario_actualizacion = self.request.user
        messages.success(self.request, "Los datos del equipo se actualizaron correctamente.")
        return super().form_valid(form)


class FichaEquipoView(AccesoEquipos, DetailView):
    model = Equipo
    template_name = "equipos/ficha.html"
    context_object_name = "equipo"
    permission_required = "cuentas.ver_equipos"

    def get_queryset(self):
        return Equipo.objects.select_related("categoria", "ambiente", "responsable").prefetch_related("historial__usuario")

    def get_context_data(self, **kwargs):
        from django.db.models import F, Sum

        from apps.intervenciones.models import Intervencion, RepuestoUsado
        from apps.solicitudes.models import Solicitud

        context = super().get_context_data(**kwargs)
        intervenciones = Intervencion.objects.filter(solicitud__equipo=self.object)
        mano_obra = intervenciones.aggregate(total=Sum("costo_mano_obra"))["total"]
        repuestos = RepuestoUsado.objects.filter(intervencion__solicitud__equipo=self.object).aggregate(total=Sum(F("cantidad") * F("costo_unitario")))["total"]
        context["costo_acumulado"] = (mano_obra or 0) + (repuestos or 0)
        context["cantidad_fallas"] = Solicitud.objects.filter(equipo=self.object).count()
        return context


class BajaEquipoView(AccesoEquipos, View):
    permission_required = ("cuentas.dar_baja_equipos", "cuentas.autorizar_baja_equipo")

    def get(self, request, pk):
        from django.shortcuts import render

        equipo = get_object_or_404(Equipo, pk=pk)
        return render(request, "equipos/confirmar_baja.html", {"equipo": equipo})

    def post(self, request, pk):
        equipo = get_object_or_404(Equipo, pk=pk)
        if equipo.estado == Equipo.Estado.DADO_DE_BAJA:
            messages.info(request, "El equipo ya está dado de baja.")
            return redirect("equipos:ficha", pk=equipo.pk)
        equipo.estado = Equipo.Estado.DADO_DE_BAJA
        equipo._usuario_actualizacion = request.user
        try:
            equipo.save(update_fields=["estado", "actualizado_en"])
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect("equipos:ficha", pk=equipo.pk)
        messages.success(request, "El equipo se dio de baja y conserva su historial.")
        return redirect("equipos:ficha", pk=equipo.pk)


class ListaCategoriasView(AccesoEquipos, ListView):
    model = CategoriaEquipo
    template_name = "equipos/categorias.html"
    context_object_name = "categorias"
    permission_required = "cuentas.editar_equipos"


class CrearCategoriaView(AccesoEquipos, CreateView):
    model = CategoriaEquipo
    form_class = CategoriaEquipoForm
    template_name = "equipos/categoria_formulario.html"
    permission_required = "cuentas.crear_equipos"
    success_url = reverse_lazy("equipos:categorias")

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        messages.success(self.request, "La categoría se creó correctamente.")
        return super().form_valid(form)


class DesactivarCategoriaView(AccesoEquipos, View):
    permission_required = "cuentas.editar_equipos"

    def post(self, request, pk):
        categoria = get_object_or_404(CategoriaEquipo, pk=pk)
        if categoria.equipos.exists():
            messages.error(request, "No se puede desactivar una categoría con equipos asignados.")
        else:
            categoria.activo = False
            categoria.save(update_fields=["activo", "actualizado_en"])
            messages.success(request, "La categoría se desactivó correctamente.")
        return redirect("equipos:categorias")