from django import forms
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError

from apps.cuentas.models import Usuario
from apps.equipos.forms import EquipoChoiceField
from apps.equipos.models import Equipo, EstadoEquipo

from .models import Solicitud


class SolicitudForm(forms.ModelForm):
    equipo = EquipoChoiceField(
        label="Equipo con falla",
        queryset=Equipo.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Si falla un teclado o mouse, elígelo: aparece con la computadora a la que pertenece.",
    )

    class Meta:
        model = Solicitud
        fields = ("docente_solicitante", "equipo", "descripcion", "prioridad")
        labels = {
            "docente_solicitante": "Docente solicitante",
            "descripcion": "Problema que presenta el equipo",
            "prioridad": "Prioridad",
        }
        help_texts = {"docente_solicitante": "Nombre del docente que pidió el reporte (los docentes no tienen cuenta)."}
        widgets = {
            "docente_solicitante": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej.: Lic. Ana Rojas", "autocomplete": "off"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Ej.: la computadora no enciende; el mouse no responde."}),
            "prioridad": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["equipo"].queryset = (
            Equipo.objects.exclude(estado__tipo=EstadoEquipo.Tipo.BAJA)
            .select_related("categoria", "ambiente", "equipo_principal")
            .order_by("ambiente__nombre", "codigo")
        )

    def clean_docente_solicitante(self):
        docente = " ".join(self.cleaned_data["docente_solicitante"].split())
        if len(docente) < 3:
            raise ValidationError("Escribe el nombre del docente que hizo el pedido.")
        return docente

    def clean_descripcion(self):
        descripcion = self.cleaned_data["descripcion"].strip()
        if len(descripcion) < 8:
            raise ValidationError("Describe el problema con al menos 8 caracteres.")
        return descripcion


class AsignarTecnicoForm(forms.Form):
    tecnico = forms.ModelChoiceField(label="Técnico", queryset=Usuario.objects.none(), widget=forms.Select(attrs={"class": "form-select"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        permiso = Permission.objects.filter(content_type__app_label="cuentas", codename="crear_intervenciones").first()
        self.fields["tecnico"].queryset = Usuario.objects.filter(is_active=True, is_superuser=False, groups__permissions=permiso).distinct().order_by("last_name", "first_name", "username") if permiso else Usuario.objects.none()


class CambiarEstadoSolicitudForm(forms.Form):
    estado = forms.ChoiceField(label="Nuevo estado", choices=Solicitud.Estado.choices, widget=forms.Select(attrs={"class": "form-select"}))
    comentario = forms.CharField(label="Comentario", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))
    motivo_cancelacion = forms.CharField(label="Motivo de cancelación", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))

    def clean(self):
        datos = super().clean()
        if datos.get("estado") == Solicitud.Estado.CANCELADA and not datos.get("motivo_cancelacion", "").strip():
            self.add_error("motivo_cancelacion", "Indica por qué se cancela la solicitud.")
        return datos