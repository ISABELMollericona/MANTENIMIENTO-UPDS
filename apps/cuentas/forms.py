from django import forms
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Rol, Usuario
from .services import validar_roles_y_estado


class UsuarioBaseForm(forms.ModelForm):
    grupos = forms.ModelMultipleChoiceField(
        label="Roles",
        queryset=Group.objects.filter(rol_sistema__isnull=False).order_by("name"),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Usuario
        fields = ("username", "first_name", "last_name", "email", "is_active", "force_password_change")
        labels = {
            "username": "Nombre de usuario",
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "email": "Correo electrónico",
            "is_active": "Cuenta activa",
            "force_password_change": "Solicitar cambio de contraseña al ingresar",
        }
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control", "autocomplete": "username"}),
            "first_name": forms.TextInput(attrs={"class": "form-control", "autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "autocomplete": "family-name"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["grupos"].initial = self.instance.groups.filter(rol_sistema__isnull=False)

    def clean(self):
        datos = super().clean()
        if "grupos" in datos and "is_active" in datos:
            try:
                validar_roles_y_estado(self.instance, datos["grupos"], datos["is_active"])
            except ValidationError as error:
                self.add_error("grupos", error)
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=commit)
        if commit:
            usuario.groups.set(self.cleaned_data["grupos"])
        return usuario


class UsuarioCreacionForm(UsuarioBaseForm):
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}))
    password2 = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}))

    class Meta(UsuarioBaseForm.Meta):
        fields = UsuarioBaseForm.Meta.fields

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Las contraseñas no coinciden.")
        validate_password(password2, self.instance)
        return password2

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["password1"])
        if commit:
            usuario.save()
            usuario.groups.set(self.cleaned_data["grupos"])
        return usuario


class RolForm(forms.ModelForm):
    permisos = forms.ModelMultipleChoiceField(
        label="Permisos",
        queryset=Permission.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Rol
        fields = ("nombre", "descripcion")
        labels = {"nombre": "Nombre del rol", "descripcion": "Descripción"}
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "maxlength": "150"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.catalogo = Permission.objects.filter(
            content_type__app_label="cuentas",
            content_type__model="catalogopermiso",
        ).order_by("codename")
        self.fields["permisos"].queryset = self.catalogo
        if self.instance.pk:
            self.fields["permisos"].initial = self.instance.grupo.permissions.filter(pk__in=self.catalogo.values("pk"))
        if self.instance.protegido:
            self.fields["nombre"].disabled = True
            self.fields["permisos"].disabled = True

    def save(self, commit=True):
        with transaction.atomic():
            rol = super().save(commit=commit)
            if commit and not rol.protegido:
                asignados = self.cleaned_data["permisos"]
                anteriores = self.catalogo.filter(group__pk=rol.grupo_id)
                rol.grupo.permissions.remove(*anteriores.exclude(pk__in=asignados.values("pk")))
                rol.grupo.permissions.add(*asignados)
            return rol
