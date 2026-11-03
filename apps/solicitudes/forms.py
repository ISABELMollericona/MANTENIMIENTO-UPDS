from django import forms
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError

from apps.cuentas.models import Usuario
from apps.equipos.models import Equipo

from .models import Solicitud


class SolicitudForm(forms.ModelForm):
    class Meta:
        model = Solicitud
        fields = ("equipo", "descripcion", "prioridad")
        labels = {"equipo": "Equipo", "descripcion": "Describe la falla", "prioridad": "Prioridad"}
        widgets = {
            "equipo": forms.Select(attrs={"class": "form-select"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "¿Qué ocurre con el equipo?"}),
            "prioridad": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["equipo"].queryset = Equipo.objects.exclude(estado=Equipo.Estado.DADO_DE_BAJA).select_related("categoria", "ambiente").order_by("codigo")

    def clean_descripcion(self):
        descripcion = self.cleaned_data["descripcion"].strip()
        if len(descripcion) < 8:
            raise ValidationError("Describe la falla con al menos 8 caracteres.")
        return descripcion


class AsignarTecnicoForm(forms.Form):
    tecnico = forms.ModelChoiceField(label="Técnico", queryset=Usuario.objects.none(), widget=forms.Select(attrs={"class": "form-select"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        permiso = Permission.objects.filter(content_type__app_label="cuentas", codename="crear_intervenciones").first()
        self.fields["tecnico"].queryset = Usuario.objects.filter(is_active=True, groups__permissions=permiso).distinct().order_by("last_name", "first_name", "username") if permiso else Usuario.objects.none()


class CambiarEstadoSolicitudForm(forms.Form):
    estado = forms.ChoiceField(label="Nuevo estado", choices=Solicitud.Estado.choices, widget=forms.Select(attrs={"class": "form-select"}))
    comentario = forms.CharField(label="Comentario", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))
    motivo_cancelacion = forms.CharField(label="Motivo de cancelación", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))

    def clean(self):
        datos = super().clean()
        if datos.get("estado") == Solicitud.Estado.CANCELADA and not datos.get("motivo_cancelacion", "").strip():
            self.add_error("motivo_cancelacion", "Indica por qué se cancela la solicitud.")
        return datos