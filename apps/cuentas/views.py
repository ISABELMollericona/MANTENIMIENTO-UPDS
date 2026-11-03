from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from .forms import RolForm, UsuarioCreacionForm, UsuarioBaseForm
from .models import Rol, Usuario
from .permissions import obtener_matriz_permisos
from .services import es_administrador, registrar_auditoria


class AccesoProtegido(LoginRequiredMixin, PermissionRequiredMixin):
    raise_exception = True


class ListaUsuariosView(AccesoProtegido, ListView):
    model = Usuario
    template_name = "cuentas/usuarios_lista.html"
    context_object_name = "usuarios"
    paginate_by = 20
    permission_required = "cuentas.ver_usuarios"

    def get_queryset(self):
        queryset = Usuario.objects.prefetch_related("groups").order_by("last_name", "first_name", "username")
        busqueda = self.request.GET.get("q", "").strip()
        estado = self.request.GET.get("estado", "")
        if busqueda:
            queryset = queryset.filter(username__icontains=busqueda) | queryset.filter(first_name__icontains=busqueda) | queryset.filter(last_name__icontains=busqueda) | queryset.filter(email__icontains=busqueda)
        if estado in {"activo", "inactivo"}:
            queryset = queryset.filter(is_active=(estado == "activo"))
        return queryset.distinct()


class CrearUsuarioView(AccesoProtegido, CreateView):
    model = Usuario
    form_class = UsuarioCreacionForm
    template_name = "cuentas/usuario_form.html"
    permission_required = ("cuentas.crear_usuarios", "cuentas.gestionar_usuarios")
    success_url = reverse_lazy("cuentas:usuarios")

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        with transaction.atomic():
            response = super().form_valid(form)
            registrar_auditoria(self.request, "usuario_creado", f"Se creó el usuario {self.object.username}.")
        messages.success(self.request, "El usuario se creó correctamente.")
        return response


class EditarUsuarioView(AccesoProtegido, UpdateView):
    model = Usuario
    form_class = UsuarioBaseForm
    template_name = "cuentas/usuario_form.html"
    permission_required = ("cuentas.editar_usuarios", "cuentas.gestionar_usuarios")
    success_url = reverse_lazy("cuentas:usuarios")

    def form_valid(self, form):
        anterior_activo = self.get_object().is_active
        anterior_roles = set(self.get_object().groups.values_list("name", flat=True))
        desactivado = anterior_activo and not form.cleaned_data["is_active"]
        if desactivado and not self.request.user.has_perm("cuentas.desactivar_usuarios") and not es_administrador(self.request.user):
            form.add_error("is_active", "No tienes permiso para desactivar usuarios.")
            return self.form_invalid(form)
        with transaction.atomic():
            response = super().form_valid(form)
            nuevos_roles = set(self.object.groups.values_list("name", flat=True))
            cambios = [f"roles: {', '.join(sorted(anterior_roles)) or 'ninguno'} -> {', '.join(sorted(nuevos_roles)) or 'ninguno'}"]
            if anterior_activo != self.object.is_active:
                cambios.append(f"activo: {anterior_activo} -> {self.object.is_active}")
            registrar_auditoria(self.request, "usuario_actualizado", f"Usuario {self.object.username}; " + "; ".join(cambios))
        messages.success(self.request, "Los datos del usuario se actualizaron correctamente.")
        return response


class ListaRolesView(AccesoProtegido, ListView):
    model = Rol
    template_name = "cuentas/roles_lista.html"
    context_object_name = "roles"
    permission_required = "cuentas.ver_roles"

    def get_queryset(self):
        return Rol.objects.select_related("grupo").prefetch_related("grupo__user_set", "grupo__permissions").order_by("nombre")


class ContextoMatrizPermisos:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        if form.is_bound:
            seleccionados = form.data.getlist("permisos")
        else:
            valores = form["permisos"].value() or []
            seleccionados = [str(valor.pk if hasattr(valor, "pk") else valor) for valor in valores]
        context["matriz_permisos"], context["permisos_especiales"] = obtener_matriz_permisos(seleccionados)
        return context


class CrearRolView(AccesoProtegido, ContextoMatrizPermisos, CreateView):
    model = Rol
    form_class = RolForm
    template_name = "cuentas/rol_form.html"
    permission_required = ("cuentas.crear_roles", "cuentas.gestionar_roles")
    success_url = reverse_lazy("cuentas:roles")

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            codenames = list(self.object.grupo.permissions.values_list("codename", flat=True))
            registrar_auditoria(self.request, "rol_creado", f"Rol {self.object.nombre}; permisos: {', '.join(sorted(codenames)) or 'ninguno'}.")
        messages.success(self.request, "El rol se creó correctamente.")
        return response


class EditarRolView(AccesoProtegido, ContextoMatrizPermisos, UpdateView):
    model = Rol
    form_class = RolForm
    template_name = "cuentas/rol_form.html"
    permission_required = ("cuentas.editar_roles", "cuentas.gestionar_roles")
    success_url = reverse_lazy("cuentas:roles")

    def form_valid(self, form):
        rol = self.get_object()
        nombre_anterior = rol.nombre
        anteriores = set(rol.grupo.permissions.values_list("codename", flat=True))
        with transaction.atomic():
            response = super().form_valid(form)
            actuales = set(self.object.grupo.permissions.values_list("codename", flat=True))
            agregados = sorted(actuales - anteriores)
            quitados = sorted(anteriores - actuales)
            detalle = f"Rol {nombre_anterior} -> {self.object.nombre}; permisos agregados: {', '.join(agregados) or 'ninguno'}; retirados: {', '.join(quitados) or 'ninguno'}."
            registrar_auditoria(self.request, "rol_actualizado", detalle)
        messages.success(self.request, "El rol y sus permisos se actualizaron correctamente.")
        return response


class EliminarRolView(AccesoProtegido, View):
    permission_required = ("cuentas.eliminar_roles", "cuentas.gestionar_roles")

    def get(self, request, pk):
        from django.shortcuts import render

        rol = get_object_or_404(Rol.objects.select_related("grupo"), pk=pk)
        return render(request, "cuentas/rol_confirmar_eliminacion.html", {"rol": rol})

    def post(self, request, pk):
        rol = get_object_or_404(Rol.objects.select_related("grupo"), pk=pk)
        nombre = rol.nombre
        try:
            rol.delete()
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect("cuentas:roles")
        registrar_auditoria(request, "rol_eliminado", f"Se eliminó el rol {nombre}.")
        messages.success(request, "El rol se eliminó correctamente.")
        return redirect("cuentas:roles")
