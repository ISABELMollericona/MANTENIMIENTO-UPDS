from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.equipos.models import Equipo


class Solicitud(models.Model):
    class Prioridad(models.TextChoices):
        ALTA = "alta", "Alta"
        MEDIA = "media", "Media"
        BAJA = "baja", "Baja"

    class Estado(models.TextChoices):
        REGISTRADA = "registrada", "Registrada"
        ASIGNADA = "asignada", "Asignada"
        EN_REPARACION = "en_reparacion", "En reparación"
        RESUELTA = "resuelta", "Resuelta"
        CANCELADA = "cancelada", "Cancelada"

    equipo = models.ForeignKey(Equipo, verbose_name="Equipo", on_delete=models.PROTECT, related_name="solicitudes")
    descripcion = models.TextField("Descripción de la falla")
    prioridad = models.CharField("Prioridad", max_length=8, choices=Prioridad.choices, default=Prioridad.MEDIA, db_index=True)
    estado = models.CharField("Estado", max_length=16, choices=Estado.choices, default=Estado.REGISTRADA, db_index=True)
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Solicitante", on_delete=models.PROTECT, related_name="solicitudes_reportadas")
    tecnico_asignado = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Técnico asignado", null=True, blank=True, on_delete=models.SET_NULL, related_name="solicitudes_asignadas")
    fecha_reporte = models.DateTimeField("Fecha de reporte", default=timezone.now, db_index=True)
    fecha_cierre = models.DateTimeField("Fecha de cierre", null=True, blank=True, db_index=True)
    motivo_cancelacion = models.TextField("Motivo de cancelación", blank=True)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)
    actualizado_en = models.DateTimeField("Actualizado en", auto_now=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Creado por", null=True, blank=True, on_delete=models.SET_NULL, related_name="solicitudes_creadas")

    class Meta:
        verbose_name = "solicitud de mantenimiento"
        verbose_name_plural = "solicitudes de mantenimiento"
        ordering = ["-fecha_reporte", "-pk"]
        indexes = [
            models.Index(fields=["estado", "prioridad", "fecha_reporte"], name="sol_estado_pri_fecha_idx"),
            models.Index(fields=["tecnico_asignado", "estado"], name="sol_tecnico_estado_idx"),
        ]

    def __str__(self):
        return f"Solicitud #{self.pk} - {self.equipo.codigo}"

    def delete(self, *args, **kwargs):
        raise ValidationError("Las solicitudes no se eliminan; deben cancelarse para conservar su historial.")


class HistorialSolicitud(models.Model):
    solicitud = models.ForeignKey(Solicitud, verbose_name="Solicitud", on_delete=models.PROTECT, related_name="historial")
    estado_anterior = models.CharField("Estado anterior", max_length=16, choices=Solicitud.Estado.choices)
    estado_nuevo = models.CharField("Estado nuevo", max_length=16, choices=Solicitud.Estado.choices)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Usuario", on_delete=models.PROTECT, related_name="cambios_solicitud")
    fecha = models.DateTimeField("Fecha", auto_now_add=True, db_index=True)
    comentario = models.TextField("Comentario", blank=True)

    class Meta:
        verbose_name = "historial de solicitud"
        verbose_name_plural = "historial de solicitudes"
        ordering = ["fecha", "pk"]

    def __str__(self):
        return f"{self.solicitud}: {self.get_estado_anterior_display()} -> {self.get_estado_nuevo_display()}"