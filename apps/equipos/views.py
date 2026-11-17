from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.ubicaciones.models import Ambiente

from .forms import BajaEquipoForm, CategoriaEquipoForm, EquipoForm, EstadoEquipoForm, InformeVicerrectoriaForm
from .models import CategoriaEquipo, Equipo, EstadoEquipo


class AccesoEquipos(LoginRequiredMixin, PermissionRequiredMixin):
    @property
    def raise_exception(self):
        # Sin sesión: redirige al login (y vuelve aquí). Con sesión y sin permiso: 403.
        return self.request.user.is_authenticated


class ListaEquiposView(AccesoEquipos, ListView):
    model = Equipo
    template_name = "equipos/lista.html"
    context_object_name = "equipos"
    paginate_by = 20
    permission_required = "cuentas.ver_equipos"

    def get_queryset(self):
        queryset = Equipo.objects.select_related("categoria", "ambiente", "estado", "equipo_principal")
        consulta = self.request.GET.get("q", "").strip()
        for campo in ("categoria", "ambiente", "estado"):
            valor = self.request.GET.get(campo, "")
            if valor.isdigit():
                queryset = queryset.filter(**{f"{campo}_id": valor})
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
        context["ambientes"] = Ambiente.laboratorios()
        context["estados"] = EstadoEquipo.objects.filter(activo=True)
        return context


class CrearEquipoView(AccesoEquipos, CreateView):
    model = Equipo
    form_class = EquipoForm
    template_name = "equipos/formulario.html"
    permission_required = "cuentas.crear_equipos"
    success_url = reverse_lazy("equipos:lista")

    def get_initial(self):
        inicial = super().get_initial()
        principal = self.request.GET.get("principal", "")
        if principal.isdigit():
            computadora = Equipo.objects.filter(pk=principal).first()
            if computadora:
                inicial.update({"equipo_principal": computadora.pk, "ambiente": computadora.ambiente_id})
                periferico = CategoriaEquipo.objects.filter(activo=True, es_periferico=True).first()
                if periferico:
                    inicial["categoria"] = periferico.pk
        return inicial

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

    def get_success_url(self):
        return reverse_lazy("equipos:ficha", args=[self.object.pk])

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
        return Equipo.objects.select_related("categoria", "ambiente", "responsable", "estado", "equipo_principal").prefetch_related("historial__usuario")

    def get_context_data(self, **kwargs):
        from apps.intervenciones.models import Intervencion
        from apps.solicitudes.models import Solicitud

        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        context["perifericos"] = self.object.perifericos.select_related("categoria", "estado").order_by("codigo")
        context["cantidad_fallas"] = Solicitud.objects.filter(equipo=self.object).count()
        # El historial de fallas y reparaciones solo lo ven quienes gestionan el mantenimiento.
        context["puede_ver_mantenimiento"] = usuario.is_superuser or usuario.has_perm("cuentas.ver_todas_solicitudes")
        if context["puede_ver_mantenimiento"]:
            context["reparaciones"] = Intervencion.objects.filter(solicitud__equipo=self.object).select_related("tecnico", "laboratorio_origen", "solicitud").order_by("-fecha_salida")
        return context


class BajaEquipoView(AccesoEquipos, View):
    """Registra el retiro del equipo y si se informó a Vicerrectoría. No es la baja oficial."""

    permission_required = ("cuentas.dar_baja_equipos", "cuentas.autorizar_baja_equipo")

    def get(self, request, pk):
        equipo = get_object_or_404(Equipo.objects.select_related("estado", "categoria", "ambiente"), pk=pk)
        if equipo.esta_de_baja:
            messages.info(request, "El equipo ya tiene registrada su baja. Puedes actualizar el informe a Vicerrectoría desde «Bajas».")
            return redirect("equipos:ficha", pk=equipo.pk)
        return render(request, "equipos/confirmar_baja.html", {"equipo": equipo, "form": BajaEquipoForm(instance=equipo), "perifericos": equipo.perifericos.exclude(estado__tipo=EstadoEquipo.Tipo.BAJA)})

    def post(self, request, pk):
        equipo = get_object_or_404(Equipo.objects.select_related("estado", "categoria", "ambiente"), pk=pk)
        if equipo.esta_de_baja:
            messages.info(request, "El equipo ya tiene registrada su baja.")
            return redirect("equipos:ficha", pk=equipo.pk)
        form = BajaEquipoForm(request.POST, instance=equipo)
        perifericos = equipo.perifericos.exclude(estado__tipo=EstadoEquipo.Tipo.BAJA)
        if not form.is_valid():
            return render(request, "equipos/confirmar_baja.html", {"equipo": equipo, "form": form, "perifericos": perifericos})
        try:
            with transaction.atomic():
                equipo = form.save(commit=False)
                equipo._usuario_actualizacion = request.user
                equipo.save()
                if form.cleaned_data.get("incluir_perifericos"):
                    for periferico in perifericos:
                        for campo in ("estado", "fecha_baja", "informado_vicerrectoria", "fecha_informe_vicerrectoria"):
                            setattr(periferico, campo, getattr(equipo, campo))
                        periferico.motivo_baja = f"Retirado junto con {equipo.codigo}. {equipo.motivo_baja}".strip()
                        periferico._usuario_actualizacion = request.user
                        periferico.save()
        except ValidationError as error:
            form.add_error(None, error)
            return render(request, "equipos/confirmar_baja.html", {"equipo": equipo, "form": form, "perifericos": perifericos})
        messages.success(request, "Se registró el retiro del equipo. Recuerda que la baja oficial la realiza Vicerrectoría Administrativa.")
        return redirect("equipos:ficha", pk=equipo.pk)


class ListaBajasView(AccesoEquipos, ListView):
    """Equipos retirados con todos sus códigos y si se informó a Vicerrectoría."""

    model = Equipo
    template_name = "equipos/bajas.html"
    context_object_name = "equipos"
    paginate_by = 30
    permission_required = "cuentas.dar_baja_equipos"

    def get_queryset(self):
        queryset = Equipo.objects.filter(estado__tipo=EstadoEquipo.Tipo.BAJA).select_related("categoria", "ambiente", "estado", "equipo_principal").prefetch_related("perifericos")
        informado = self.request.GET.get("informado", "")
        if informado in {"si", "no"}:
            queryset = queryset.filter(informado_vicerrectoria=(informado == "si"))
        return queryset.order_by("-fecha_baja", "codigo")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pendientes_informar"] = Equipo.objects.filter(estado__tipo=EstadoEquipo.Tipo.BAJA, informado_vicerrectoria=False).count()
        context["puede_marcar"] = self.request.user.has_perm("cuentas.autorizar_baja_equipo")
        return context


class InformeVicerrectoriaView(AccesoEquipos, View):
    permission_required = ("cuentas.dar_baja_equipos", "cuentas.autorizar_baja_equipo")

    def post(self, request, pk):
        equipo = get_object_or_404(Equipo.objects.select_related("estado"), pk=pk, estado__tipo=EstadoEquipo.Tipo.BAJA)
        form = InformeVicerrectoriaForm(request.POST, instance=equipo)
        if form.is_valid():
            equipo = form.save(commit=False)
            equipo._usuario_actualizacion = request.user
            equipo.save()
            messages.success(request, f"Se actualizó el informe a Vicerrectoría de {equipo.codigo}.")
        else:
            errores = [error for lista in form.errors.values() for error in lista]
            messages.error(request, f"{equipo.codigo}: {' '.join(errores)}")
        return redirect("equipos:bajas")


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


class ListaEstadosView(AccesoEquipos, ListView):
    """Estados de equipo editables (pendientes de aprobación final del cliente)."""

    model = EstadoEquipo
    template_name = "equipos/estados.html"
    context_object_name = "estados"
    permission_required = "cuentas.editar_equipos"


class CrearEstadoView(AccesoEquipos, CreateView):
    model = EstadoEquipo
    form_class = EstadoEquipoForm
    template_name = "equipos/estado_formulario.html"
    permission_required = "cuentas.editar_equipos"
    success_url = reverse_lazy("equipos:estados")

    def form_valid(self, form):
        messages.success(self.request, "El estado se creó correctamente.")
        return super().form_valid(form)


class EditarEstadoView(AccesoEquipos, UpdateView):
    model = EstadoEquipo
    form_class = EstadoEquipoForm
    template_name = "equipos/estado_formulario.html"
    permission_required = "cuentas.editar_equipos"
    success_url = reverse_lazy("equipos:estados")

    def form_valid(self, form):
        messages.success(self.request, "El estado se actualizó. Los equipos que lo tienen muestran el nuevo nombre.")
        return super().form_valid(form)
