from django import forms
from django.utils import timezone

from .models import Intervencion


class IntervencionForm(forms.ModelForm):
    """Reparación: salida del equipo, trabajo realizado, repuestos y devolución."""

    class Meta:
        model = Intervencion
        fields = ("fecha_salida", "diagnostico", "trabajo_realizado", "repuestos_usados", "fecha_devolucion", "resultado", "observaciones")
        labels = {
            "fecha_salida": "Fecha de salida",
            "diagnostico": "Diagnóstico",
            "trabajo_realizado": "Trabajo realizado",
            "repuestos_usados": "Repuestos usados",
            "fecha_devolucion": "Fecha de devolución (al terminar)",
            "resultado": "Resultado (al terminar)",
            "observaciones": "Observaciones",
        }
        widgets = {
            "fecha_salida": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "diagnostico": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "¿Qué tiene el equipo?"}),
            "trabajo_realizado": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "repuestos_usados": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Ej.: fuente de poder 500 W; cable SATA"}),
            "fecha_devolucion": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "resultado": forms.Select(attrs={"class": "form-select"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, solicitud=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.solicitud = solicitud
        self.fields["fecha_salida"].required = True
        hoy = timezone.localdate().isoformat()
        self.fields["fecha_salida"].widget.attrs["max"] = hoy
        self.fields["fecha_devolucion"].widget.attrs["max"] = hoy
        if not self.instance.pk and not self.initial.get("fecha_salida"):
            self.initial["fecha_salida"] = timezone.localdate()

    def _post_clean(self):
        # Si la fecha de devolución ya tiene un error del formulario, el modelo la ve vacía y
        # añadiría «Indica la fecha de devolución…», que confunde: se deja solo el error real.
        super()._post_clean()
        errores = self.errors.get("fecha_devolucion")
        duplicado = "Indica la fecha de devolución junto con el resultado."
        if errores and len(errores) > 1 and duplicado in errores:
            self.errors["fecha_devolucion"] = self.error_class([e for e in errores if e != duplicado])

    def clean_diagnostico(self):
        diagnostico = self.cleaned_data["diagnostico"].strip()
        if len(diagnostico) < 5:
            raise forms.ValidationError("Escribe el diagnóstico del equipo.")
        return diagnostico

    def clean(self):
        datos = super().clean()
        salida, devolucion, resultado = datos.get("fecha_salida"), datos.get("fecha_devolucion"), datos.get("resultado")
        if salida and self.solicitud and salida < timezone.localtime(self.solicitud.fecha_reporte).date():
            self.add_error("fecha_salida", f"El equipo no puede salir antes del reporte de falla ({timezone.localtime(self.solicitud.fecha_reporte):%d/%m/%Y}).")
        if salida and devolucion and devolucion < salida:
            self.add_error("fecha_devolucion", "La fecha de devolución debe ser igual o posterior a la fecha de salida.")
        if devolucion and not resultado:
            self.add_error("resultado", "Selecciona el resultado al registrar la devolución.")
        if resultado and not devolucion and "fecha_devolucion" not in self.errors:
            self.add_error("fecha_devolucion", "Indica la fecha de devolución junto con el resultado.")
        if devolucion and not (datos.get("trabajo_realizado") or "").strip():
            self.add_error("trabajo_realizado", "Describe el trabajo realizado antes de devolver el equipo.")
        return datos
