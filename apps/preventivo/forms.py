from django import forms
from django.contrib.auth.models import Permission
from django.db.models import Q
from django.utils import timezone

from apps.cuentas.models import Usuario
from apps.ubicaciones.models import Ambiente

from .models import MantenimientoPreventivo


def tecnicos_disponibles():
    permiso = Permission.objects.filter(content_type__app_label="cuentas", codename="editar_preventivos").first()
    if not permiso:
        return Usuario.objects.none()
    return (
        Usuario.objects.filter(is_active=True)
        .filter(Q(groups__permissions=permiso) | Q(user_permissions=permiso))
        .distinct()
        .order_by("last_name", "first_name", "username")
    )


class CronogramaForm(forms.Form):
    """Cronograma anual de un laboratorio: 2 o 3 mantenimientos preventivos."""

    laboratorio = forms.ModelChoiceField(label="Laboratorio", queryset=Ambiente.objects.none(), widget=forms.Select(attrs={"class": "form-select"}))
    anio = forms.IntegerField(label="Año", min_value=2020, max_value=2100, widget=forms.NumberInput(attrs={"class": "form-control"}))
    fecha_1 = forms.DateField(label="1.er mantenimiento", widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"))
    fecha_2 = forms.DateField(label="2.º mantenimiento", widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"))
    fecha_3 = forms.DateField(label="3.er mantenimiento (opcional)", required=False, widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"))
    tecnico = forms.ModelChoiceField(label="Técnico (opcional)", queryset=Usuario.objects.none(), required=False, empty_label="Sin asignar", widget=forms.Select(attrs={"class": "form-select"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["laboratorio"].queryset = Ambiente.laboratorios()
        self.fields["tecnico"].queryset = tecnicos_disponibles()
        self.initial.setdefault("anio", timezone.localdate().year)

    def clean(self):
        datos = super().clean()
        anio = datos.get("anio")
        fechas = [(numero, datos.get(f"fecha_{numero}")) for numero in (1, 2, 3)]
        anteriores = None
        for numero, fecha in fechas:
            if not fecha:
                continue
            if anio and fecha.year != anio:
                self.add_error(f"fecha_{numero}", f"La fecha debe estar dentro del año {anio}.")
            elif anteriores and fecha <= anteriores:
                self.add_error(f"fecha_{numero}", "Cada mantenimiento debe ser posterior al anterior.")
            anteriores = fecha
        laboratorio = datos.get("laboratorio")
        if laboratorio and anio and not datos.get("fecha_3"):
            tercero = MantenimientoPreventivo.objects.filter(laboratorio=laboratorio, anio=anio, numero=3, estado=MantenimientoPreventivo.Estado.REALIZADO).exists()
            if tercero:
                self.add_error("fecha_3", "El 3.er mantenimiento ya se realizó; no se puede quitar.")
        return datos


class MarcarRealizadoForm(forms.ModelForm):
    class Meta:
        model = MantenimientoPreventivo
        fields = ("fecha_realizada", "observaciones")
        labels = {"fecha_realizada": "Fecha en que se realizó", "observaciones": "Observaciones (qué se hizo)"}
        widgets = {
            "fecha_realizada": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha_realizada"].required = True
        self.fields["fecha_realizada"].widget.attrs["max"] = timezone.localdate().isoformat()
        if not self.initial.get("fecha_realizada"):
            self.initial["fecha_realizada"] = timezone.localdate()

    def clean_fecha_realizada(self):
        fecha = self.cleaned_data["fecha_realizada"]
        if fecha > timezone.localdate():
            raise forms.ValidationError("La fecha de realización no puede ser futura.")
        return fecha
