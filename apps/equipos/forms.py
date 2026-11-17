from typing import cast

from django import forms
from django.utils import timezone

from apps.cuentas.models import Usuario
from apps.ubicaciones.models import Ambiente

from .models import CategoriaEquipo, Equipo, EstadoEquipo


class EquipoChoiceField(forms.ModelChoiceField):
    """Muestra los periféricos con la computadora a la que pertenecen."""

    def label_from_instance(self, obj):
        return obj.etiqueta_completa


class CategoriaEquipoForm(forms.ModelForm):
    class Meta:
        model = CategoriaEquipo
        fields = ("nombre", "descripcion", "es_periferico")
        labels = {"nombre": "Nombre de la categoría", "descripcion": "Descripción", "es_periferico": "Es un periférico (teclado, mouse) que se asocia a una computadora"}
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "es_periferico": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class EstadoEquipoForm(forms.ModelForm):
    class Meta:
        model = EstadoEquipo
        fields = ("nombre", "tipo", "orden", "activo")
        labels = {"nombre": "Nombre del estado", "tipo": "¿Cómo lo trata el sistema?", "orden": "Orden en las listas", "activo": "Activo"}
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "orden": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        datos = super().clean()
        tipo, activo = datos.get("tipo"), datos.get("activo")
        if self.instance.pk and (tipo != self.instance.tipo or not activo):
            otros = EstadoEquipo.objects.filter(tipo=self.instance.tipo, activo=True).exclude(pk=self.instance.pk)
            if not otros.exists():
                raise forms.ValidationError(
                    f"Debe quedar al menos un estado activo de tipo «{self.instance.get_tipo_display()}». Crea otro antes de cambiar este."
                )
        return datos


class EquipoForm(forms.ModelForm):
    equipo_principal = EquipoChoiceField(queryset=Equipo.objects.none(), required=False, label="Computadora asociada (solo periféricos)", widget=forms.Select(attrs={"class": "form-select"}))

    class Meta:
        model = Equipo
        fields = ("codigo", "categoria", "marca", "modelo", "numero_serie", "fecha_compra", "ambiente", "equipo_principal", "estado", "responsable", "observaciones")
        labels = {
            "codigo": "Código de inventario", "categoria": "Categoría", "marca": "Marca", "modelo": "Modelo",
            "numero_serie": "Número de serie", "fecha_compra": "Fecha de compra", "ambiente": "Laboratorio",
            "estado": "Estado", "responsable": "Responsable (opcional)", "observaciones": "Observaciones",
        }
        widgets = {
            "codigo": forms.TextInput(attrs={"class": "form-control"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "marca": forms.TextInput(attrs={"class": "form-control"}),
            "modelo": forms.TextInput(attrs={"class": "form-control"}),
            "numero_serie": forms.TextInput(attrs={"class": "form-control"}),
            "fecha_compra": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "ambiente": forms.Select(attrs={"class": "form-select"}),
            "estado": forms.Select(attrs={"class": "form-select"}),
            "responsable": forms.Select(attrs={"class": "form-select"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categoria = cast(forms.ModelChoiceField, self.fields["categoria"])
        ambiente = cast(forms.ModelChoiceField, self.fields["ambiente"])
        responsable = cast(forms.ModelChoiceField, self.fields["responsable"])
        estado = cast(forms.ModelChoiceField, self.fields["estado"])
        principal = cast(forms.ModelChoiceField, self.fields["equipo_principal"])
        categoria.queryset = CategoriaEquipo.objects.filter(activo=True).order_by("nombre")
        ambiente.queryset = Ambiente.laboratorios()
        ambiente.required = True
        ambiente.empty_label = "Selecciona el laboratorio"
        responsable.queryset = Usuario.objects.filter(is_active=True).order_by("last_name", "first_name", "username")
        responsable.required = False
        responsable.empty_label = "Sin asignar"
        computadoras = Equipo.objects.filter(categoria__es_periferico=False).exclude(estado__tipo=EstadoEquipo.Tipo.BAJA).select_related("categoria").order_by("codigo")
        if self.instance.pk:
            computadoras = computadoras.exclude(pk=self.instance.pk)
        principal.queryset = computadoras
        principal.empty_label = "No es periférico"
        if self.instance.pk and self.instance.esta_de_baja:
            # La baja se registra con su propio formulario (motivo e informe a Vicerrectoría).
            estado.queryset = EstadoEquipo.objects.filter(pk=self.instance.estado_id)
            estado.disabled = True
        else:
            estado.queryset = EstadoEquipo.objects.filter(activo=True).exclude(tipo=EstadoEquipo.Tipo.BAJA)
            estado.empty_label = None
            estado.help_text = "Para retirar el equipo usa «Registrar baja» en su ficha."

    def clean_fecha_compra(self):
        fecha = self.cleaned_data.get("fecha_compra")
        if fecha and fecha > timezone.localdate():
            raise forms.ValidationError("La fecha de compra no puede ser futura.")
        return fecha

    def clean(self):
        datos = super().clean()
        categoria, principal = datos.get("categoria"), datos.get("equipo_principal")
        if principal and categoria and not categoria.es_periferico:
            self.add_error("equipo_principal", "Solo los periféricos (teclado, mouse) se asocian a una computadora. Deja este campo vacío o cambia la categoría.")
        return datos


class BajaEquipoForm(forms.ModelForm):
    """Registra el retiro del equipo. La baja oficial la hace Vicerrectoría fuera del sistema."""

    incluir_perifericos = forms.BooleanField(
        label="Retirar también sus periféricos (teclado, mouse) con la misma información",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = Equipo
        fields = ("estado", "fecha_baja", "motivo_baja", "informado_vicerrectoria", "fecha_informe_vicerrectoria")
        labels = {
            "estado": "Estado de baja",
            "fecha_baja": "Fecha de retiro",
            "motivo_baja": "Motivo del retiro",
            "informado_vicerrectoria": "Ya se informó a Vicerrectoría Administrativa",
            "fecha_informe_vicerrectoria": "Fecha del informe a Vicerrectoría",
        }
        widgets = {
            "estado": forms.Select(attrs={"class": "form-select"}),
            "fecha_baja": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "motivo_baja": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Ej.: placa madre dañada, no reparable; equipo obsoleto."}),
            "informado_vicerrectoria": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "fecha_informe_vicerrectoria": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estado = cast(forms.ModelChoiceField, self.fields["estado"])
        estado.queryset = EstadoEquipo.objects.filter(activo=True, tipo=EstadoEquipo.Tipo.BAJA)
        estado.empty_label = None
        self.fields["fecha_baja"].required = True
        self.fields["motivo_baja"].required = True
        if not self.instance.fecha_baja and not self.is_bound:
            self.initial["fecha_baja"] = timezone.localdate()
        if not self.instance.perifericos.exclude(estado__tipo=EstadoEquipo.Tipo.BAJA).exists():
            del self.fields["incluir_perifericos"]

    def clean_fecha_baja(self):
        fecha = self.cleaned_data.get("fecha_baja")
        if fecha and fecha > timezone.localdate():
            raise forms.ValidationError("La fecha de retiro no puede ser futura.")
        return fecha

    def clean_fecha_informe_vicerrectoria(self):
        fecha = self.cleaned_data.get("fecha_informe_vicerrectoria")
        if fecha and fecha > timezone.localdate():
            raise forms.ValidationError("La fecha del informe no puede ser futura.")
        return fecha


class InformeVicerrectoriaForm(forms.ModelForm):
    """Para marcar más tarde que la baja ya se informó a Vicerrectoría."""

    class Meta:
        model = Equipo
        fields = ("informado_vicerrectoria", "fecha_informe_vicerrectoria")
        labels = {"informado_vicerrectoria": "Informado a Vicerrectoría", "fecha_informe_vicerrectoria": "Fecha del informe"}
        widgets = {
            "informado_vicerrectoria": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "fecha_informe_vicerrectoria": forms.DateInput(attrs={"class": "form-control form-control-sm", "type": "date"}, format="%Y-%m-%d"),
        }

    def clean_fecha_informe_vicerrectoria(self):
        fecha = self.cleaned_data.get("fecha_informe_vicerrectoria")
        if fecha and fecha > timezone.localdate():
            raise forms.ValidationError("La fecha del informe no puede ser futura.")
        return fecha
