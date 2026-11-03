from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.equipos.models import CategoriaEquipo, Equipo


class PlanPreventivo(models.Model):
    categoria = models.ForeignKey(CategoriaEquipo, verbose_name="Categoría de equipo", on_delete=models.PROTECT, related_name="planes_preventivos")
    nombre = models.CharField("Nombre del plan", max_length=140)
    periodicidad_meses = models.PositiveSmallIntegerField("Periodicidad (meses)", validators=[MinValueValidator(1)])
    actividades = models.TextField("Actividades", help_text="Describe las comprobaciones y tareas del plan.")
    activo = models.BooleanField("Activo", default=True, db_index=True)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)
    actualizado_en = models.DateTimeField("Actualizado en", auto_now=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Creado por", null=True, blank=True, on_delete=models.SET_NULL, related_name="planes_preventivos_creados")

    class Meta:
        verbose_name = "plan preventivo"
        verbose_name_plural = "planes preventivos"
        ordering = ["categoria__nombre", "nombre"]
        constraints = [models.UniqueConstraint(fields=["categoria", "nombre"], name="plan_categoria_nombre_uniq")]

    def __str__(self):
        return f"{self.nombre} ({self.categoria})"

    def delete(self, *args, **kwargs):
        raise ValidationError("Los planes no se eliminan; desactívalos para conservar su historial.")


class MantenimientoProgramado(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        REALIZADO = "realizado", "Realizado"
        CANCELADO = "cancelado", "Cancelado"

    equipo = models.ForeignKey(Equipo, verbose_name="Equipo", on_delete=models.PROTECT, related_name="mantenimientos_programados")
    plan = models.ForeignKey(PlanPreventivo, verbose_name="Plan", on_delete=models.PROTECT, related_name="programaciones")
    fecha_programada = models.DateField("Fecha programada", db_index=True)
    tecnico = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Responsable técnico", null=True, blank=True, on_delete=models.SET_NULL, related_name="mantenimientos_preventivos_asignados")
    estado = models.CharField("Estado", max_length=12, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True)
    fecha_realizada = models.DateField("Fecha realizada", null=True, blank=True)
    observaciones = models.TextField("Observaciones", blank=True)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)
    actualizado_en = models.DateTimeField("Actualizado en", auto_now=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Creado por", null=True, blank=True, on_delete=models.SET_NULL, related_name="mantenimientos_preventivos_creados")
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Actualizado por", null=True, blank=True, on_delete=models.SET_NULL, related_name="mantenimientos_preventivos_actualizados")

    class Meta:
        verbose_name = "mantenimiento programado"
        verbose_name_plural = "mantenimientos programados"
        ordering = ["fecha_programada", "equipo__codigo"]
        indexes = [models.Index(fields=["estado", "fecha_programada"], name="prev_estado_fecha_idx")]
        constraints = [models.UniqueConstraint(fields=["equipo", "plan", "fecha_programada"], name="prev_equipo_plan_fecha_uniq")]

    def __str__(self):
        return f"{self.equipo.codigo} · {self.plan.nombre} · {self.fecha_programada:%d/%m/%Y}"

    @property
    def vencido(self):
        return self.estado == self.Estado.PENDIENTE and self.fecha_programada < timezone.localdate()

    def clean(self):
        if self.equipo_id and self.plan_id and self.equipo.categoria_id != self.plan.categoria_id:
            raise ValidationError({"plan": "El plan debe corresponder a la categoría del equipo."})

    def delete(self, *args, **kwargs):
        raise ValidationError("Los mantenimientos programados no se eliminan; cambia su estado a cancelado.")