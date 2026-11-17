from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.ubicaciones.models import Ambiente


class MantenimientoPreventivo(models.Model):
    """Un mantenimiento del cronograma anual de un laboratorio (2 o 3 por año)."""

    MAXIMO_POR_ANIO = 3

    class Numero(models.IntegerChoices):
        PRIMERO = 1, "1.er mantenimiento"
        SEGUNDO = 2, "2.º mantenimiento"
        TERCERO = 3, "3.er mantenimiento"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        REALIZADO = "realizado", "Realizado"

    laboratorio = models.ForeignKey(Ambiente, verbose_name="Laboratorio", on_delete=models.PROTECT, related_name="mantenimientos_preventivos")
    anio = models.PositiveSmallIntegerField("Año", db_index=True)
    numero = models.PositiveSmallIntegerField("Mantenimiento", choices=Numero.choices)
    fecha_programada = models.DateField("Fecha programada", db_index=True)
    tecnico = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Técnico", null=True, blank=True, on_delete=models.SET_NULL, related_name="mantenimientos_preventivos_asignados")
    estado = models.CharField("Estado", max_length=12, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True)
    fecha_realizada = models.DateField("Fecha en que se realizó", null=True, blank=True)
    observaciones = models.TextField("Observaciones", blank=True)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)
    actualizado_en = models.DateTimeField("Actualizado en", auto_now=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Creado por", null=True, blank=True, on_delete=models.SET_NULL, related_name="mantenimientos_preventivos_creados")
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Actualizado por", null=True, blank=True, on_delete=models.SET_NULL, related_name="mantenimientos_preventivos_actualizados")

    class Meta:
        verbose_name = "mantenimiento preventivo"
        verbose_name_plural = "mantenimientos preventivos"
        ordering = ["anio", "laboratorio__nombre", "numero"]
        constraints = [models.UniqueConstraint(fields=["laboratorio", "anio", "numero"], name="prev_lab_anio_numero_uniq")]
        indexes = [models.Index(fields=["estado", "fecha_programada"], name="prev_estado_fecha_idx")]

    def __str__(self):
        return f"{self.laboratorio.nombre} · {self.anio} · {self.get_numero_display()}"

    @property
    def vencido(self):
        return self.estado == self.Estado.PENDIENTE and self.fecha_programada < timezone.localdate()

    def clean(self):
        errores = {}
        if self.fecha_programada and self.anio and self.fecha_programada.year != self.anio:
            errores["fecha_programada"] = f"La fecha debe estar dentro del año {self.anio}."
        if self.fecha_realizada and self.fecha_realizada > timezone.localdate():
            errores["fecha_realizada"] = "La fecha de realización no puede ser futura."
        if self.estado == self.Estado.REALIZADO and not self.fecha_realizada:
            errores["fecha_realizada"] = "Indica la fecha en que se realizó."
        if errores:
            raise ValidationError(errores)
