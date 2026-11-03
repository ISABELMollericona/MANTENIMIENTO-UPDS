from django.conf import settings
from django.db import models


class Ambiente(models.Model):
    class Tipo(models.TextChoices):
        LABORATORIO = "laboratorio", "Laboratorio"
        AULA = "aula", "Aula"
        SALA_AUDIOVISUAL = "sala_audiovisual", "Sala audiovisual"
        OFICINA = "oficina", "Oficina"
        OTRO = "otro", "Otro"

    nombre = models.CharField("Nombre", max_length=140)
    tipo = models.CharField("Tipo", max_length=24, choices=Tipo.choices, db_index=True)
    bloque = models.CharField("Bloque o edificio", max_length=120, db_index=True)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Responsable", null=True, blank=True, on_delete=models.SET_NULL, related_name="ambientes_responsable")
    activo = models.BooleanField("Activo", default=True, db_index=True)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)
    actualizado_en = models.DateTimeField("Actualizado en", auto_now=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Creado por", null=True, blank=True, on_delete=models.SET_NULL, related_name="ambientes_creados")

    class Meta:
        verbose_name = "ambiente"
        verbose_name_plural = "ambientes"
        ordering = ["bloque", "nombre"]
        indexes = [models.Index(fields=["tipo", "bloque", "activo"], name="amb_tipo_bloque_act_idx")]

    def __str__(self):
        return f"{self.nombre} ({self.bloque})"