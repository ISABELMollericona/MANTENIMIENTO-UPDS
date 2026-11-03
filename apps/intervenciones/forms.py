from django import forms
from django.forms import inlineformset_factory

from .models import Intervencion, RepuestoUsado


class IntervencionForm(forms.ModelForm):
    class Meta:
        model = Intervencion
        fields = ("diagnostico", "trabajo_realizado", "fecha_inicio", "fecha_fin", "costo_mano_obra", "resultado", "observaciones")
        labels = {
            "diagnostico": "Diagnóstico", "trabajo_realizado": "Trabajo realizado",
            "fecha_inicio": "Fecha de inicio", "fecha_fin": "Fecha de fin (al terminar)",
            "costo_mano_obra": "Costo de mano de obra (Bs.)", "resultado": "Resultado (al terminar)", "observaciones": "Observaciones",
        }
        widgets = {
            "diagnostico": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "trabajo_realizado": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "fecha_inicio": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"class": "form-control", "type": "datetime-local"}),
            "fecha_fin": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"class": "form-control", "type": "datetime-local"}),
            "costo_mano_obra": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "0.01"}),
            "resultado": forms.Select(attrs={"class": "form-select"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def clean(self):
        datos = super().clean()
        fin = datos.get("fecha_fin")
        if fin and not datos.get("resultado"):
            self.add_error("resultado", "Selecciona el resultado para terminar la intervención.")
        if not fin and datos.get("resultado"):
            self.add_error("fecha_fin", "Indica la fecha de fin junto con el resultado.")
        return datos


class RepuestoUsadoForm(forms.ModelForm):
    class Meta:
        model = RepuestoUsado
        fields = ("descripcion", "cantidad", "costo_unitario")
        labels = {"descripcion": "Repuesto", "cantidad": "Cantidad", "costo_unitario": "Costo unitario (Bs.)"}
        widgets = {
            "descripcion": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre del repuesto"}),
            "cantidad": forms.NumberInput(attrs={"class": "form-control", "min": "0.01", "step": "0.01"}),
            "costo_unitario": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "0.01"}),
        }


RepuestoUsadoFormSet = inlineformset_factory(
    Intervencion,
    RepuestoUsado,
    form=RepuestoUsadoForm,
    extra=1,
    can_delete=True,
    max_num=15,
    validate_max=True,
)