from django import forms

from apps.cuentas.models import Usuario

from .models import Ambiente


class AmbienteForm(forms.ModelForm):
    class Meta:
        model = Ambiente
        fields = ("nombre", "tipo", "bloque", "responsable")
        labels = {"nombre": "Nombre del ambiente", "tipo": "Tipo", "bloque": "Bloque o edificio", "responsable": "Responsable"}
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "bloque": forms.TextInput(attrs={"class": "form-control"}),
            "responsable": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsable"].queryset = Usuario.objects.filter(is_active=True).order_by("last_name", "first_name", "username")
        self.fields["responsable"].required = False
        self.fields["responsable"].empty_label = "Sin responsable"