from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Sum
from django.utils import timezone

from apps.solicitudes.models import Solicitud


class Intervencion(models.Model):
    class Resultado(models.TextChoices):
        REPARADO = "reparado", "Reparado"
        PARCIAL = "parcial", "Parcial"
        NO_REPARABLE = "no_reparable", "No reparable"

    solicitud = models.ForeignKey(Solicitud, verbose_name="Solicitud", on_delete=models.PROTECT, related_name="intervenciones")
    tecnico = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Técnico", on_delete=models.PROTECT, related_name="intervenciones_realizadas")
    diagnostico = models.TextField("Diagnóstico")
    trabajo_realizado = models.TextField("Trabajo realizado", blank=True)
    fecha_inicio = models.DateTimeField("Fecha de inicio", default=timezone.now, db_index=True)
    fecha_fin = models.DateTimeField("Fecha de fin", null=True, blank=True)
    costo_mano_obra = models.DecimalField("Costo de mano de obra (Bs.)", max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])
    resultado = models.CharField("Resultado", max_length=16, choices=Resultado.choices, blank=True)
    observaciones = models.TextField("Observaciones", blank=True)
    uuid_cliente = models.UUIDField("UUID del cliente", null=True, blank=True, unique=True, db_index=True)
    creado_sin_conexion = models.BooleanField("Creado sin conexión", default=False)
    fecha_cliente = models.DateTimeField("Fecha del cliente", null=True, blank=True)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)
    actualizado_en = models.DateTimeField("Actualizado en", auto_now=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Creado por", null=True, blank=True, on_delete=models.SET_NULL, related_name="intervenciones_creadas")

    class Meta:
        verbose_name = "intervención"
        verbose_name_plural = "intervenciones"
        ordering = ["fecha_inicio", "pk"]
        indexes = [models.Index(fields=["tecnico", "fecha_inicio"], name="int_tecnico_inicio_idx")]

    def __str__(self):
        return f"Intervención #{self.pk} - {self.solicitud}"

    def clean(self):
        if self.fecha_fin and self.fecha_inicio and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({"fecha_fin": "La fecha de fin debe ser posterior al inicio."})
        if self.fecha_fin and not self.resultado:
            raise ValidationError({"resultado": "Selecciona un resultado para cerrar la intervención."})

    @property
    def costo_total(self):
        repuestos = self.repuestos.aggregate(total=Sum(F("cantidad") * F("costo_unitario")))["total"] or Decimal("0.00")
        return self.costo_mano_obra + repuestos


class RepuestoUsado(models.Model):
    intervencion = models.ForeignKey(Intervencion, verbose_name="Intervención", on_delete=models.PROTECT, related_name="repuestos")
    descripcion = models.CharField("Descripción del repuesto", max_length=180)
    cantidad = models.DecimalField("Cantidad", max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    costo_unitario = models.DecimalField("Costo unitario (Bs.)", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])

    class Meta:
        verbose_name = "repuesto usado"
        verbose_name_plural = "repuestos usados"
        ordering = ["pk"]

    def __str__(self):
        return f"{self.descripcion} x {self.cantidad}"

    @property
    def costo_total(self):
        return self.cantidad * self.costo_unitario