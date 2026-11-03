from django import forms

from apps.cuentas.models import Usuario
from apps.equipos.models import CategoriaEquipo, Equipo

from .models import MantenimientoProgramado, PlanPreventivo


class PlanPreventivoForm(forms.ModelForm):
    class Meta:
        model = PlanPreventivo
        fields = ("categoria", "nombre", "periodicidad_meses", "actividades", "activo")
        labels = {"categoria": "Categoría", "nombre": "Nombre del plan", "periodicidad_meses": "Periodicidad en meses", "actividades": "Actividades del plan", "activo": "Plan activo"}
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "periodicidad_meses": forms.NumberInput(attrs={"class": "form-control", "min": "1", "step": "1"}),
            "actividades": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = CategoriaEquipo.objects.filter(activo=True).order_by("nombre")


class MantenimientoProgramadoForm(forms.ModelForm):
    class Meta:
        model = MantenimientoProgramado
        fields = ("equipo", "plan", "fecha_programada", "tecnico", "observaciones")
        labels = {"equipo": "Equipo", "plan": "Plan preventivo", "fecha_programada": "Fecha programada", "tecnico": "Responsable técnico", "observaciones": "Observaciones"}
        widgets = {
            "equipo": forms.Select(attrs={"class": "form-select"}),
            "plan": forms.Select(attrs={"class": "form-select"}),
            "fecha_programada": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "tecnico": forms.Select(attrs={"class": "form-select"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["equipo"].queryset = Equipo.objects.exclude(estado=Equipo.Estado.DADO_DE_BAJA).select_related("categoria").order_by("codigo")
        self.fields["plan"].queryset = PlanPreventivo.objects.filter(activo=True).select_related("categoria").order_by("nombre")
        self.fields["tecnico"].queryset = Usuario.objects.filter(is_active=True).order_by("last_name", "first_name", "username")
        self.fields["tecnico"].required = False
        self.fields["tecnico"].empty_label = "Sin asignar"

    def clean(self):
        datos = super().clean()
        equipo, plan = datos.get("equipo"), datos.get("plan")
        if equipo and plan and equipo.categoria_id != plan.categoria_id:
            self.add_error("plan", "El plan debe corresponder a la categoría del equipo.")
        return datos