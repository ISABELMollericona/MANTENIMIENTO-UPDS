from django import forms

from apps.cuentas.models import Usuario
from apps.ubicaciones.models import Ambiente

from .models import CategoriaEquipo, Equipo


class CategoriaEquipoForm(forms.ModelForm):
    class Meta:
        model = CategoriaEquipo
        fields = ("nombre", "descripcion")
        labels = {"nombre": "Nombre de la categoría", "descripcion": "Descripción"}
        widgets = {"nombre": forms.TextInput(attrs={"class": "form-control"}), "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3})}


class EquipoForm(forms.ModelForm):
    class Meta:
        model = Equipo
        fields = ("codigo", "categoria", "marca", "modelo", "numero_serie", "fecha_compra", "costo_compra", "ambiente", "responsable", "estado", "observaciones")
        labels = {
            "codigo": "Código", "categoria": "Categoría", "marca": "Marca", "modelo": "Modelo",
            "numero_serie": "Número de serie", "fecha_compra": "Fecha de compra", "costo_compra": "Costo de compra (Bs.)",
            "ambiente": "Ambiente", "responsable": "Responsable", "estado": "Estado", "observaciones": "Observaciones",
        }
        widgets = {
            "codigo": forms.TextInput(attrs={"class": "form-control"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "marca": forms.TextInput(attrs={"class": "form-control"}),
            "modelo": forms.TextInput(attrs={"class": "form-control"}),
            "numero_serie": forms.TextInput(attrs={"class": "form-control"}),
            "fecha_compra": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "costo_compra": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "0.01"}),
            "ambiente": forms.Select(attrs={"class": "form-select"}),
            "responsable": forms.Select(attrs={"class": "form-select"}),
            "estado": forms.Select(attrs={"class": "form-select"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = CategoriaEquipo.objects.filter(activo=True).order_by("nombre")
        self.fields["ambiente"].queryset = Ambiente.objects.filter(activo=True).order_by("bloque", "nombre")
        self.fields["responsable"].queryset = Usuario.objects.filter(is_active=True).order_by("last_name", "first_name", "username")
        if self.instance.estado == Equipo.Estado.DADO_DE_BAJA:
            self.fields["estado"].choices = [(Equipo.Estado.DADO_DE_BAJA, Equipo.Estado.DADO_DE_BAJA.label)]
            self.fields["estado"].disabled = True
        else:
            self.fields["estado"].choices = [choice for choice in Equipo.Estado.choices if choice[0] != Equipo.Estado.DADO_DE_BAJA]
        for campo in ("ambiente", "responsable"):
            self.fields[campo].required = False
            self.fields[campo].empty_label = "Sin asignar"

    def clean_costo_compra(self):
        costo = self.cleaned_data.get("costo_compra")
        if costo is not None and costo < 0:
            raise forms.ValidationError("El costo no puede ser negativo.")
        return costo