from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.solicitudes.models import Solicitud
from apps.ubicaciones.models import Ambiente


class Intervencion(models.Model):
    """Reparación (mantenimiento correctivo) originada por un reporte de falla."""

    class Resultado(models.TextChoices):
        REPARADO = "reparado", "Reparado"
        PARCIAL = "parcial", "Reparado parcialmente"
        NO_REPARABLE = "no_reparable", "No reparable"

    solicitud = models.ForeignKey(Solicitud, verbose_name="Reporte de falla", on_delete=models.PROTECT, related_name="intervenciones")
    tecnico = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Técnico", on_delete=models.PROTECT, related_name="intervenciones_realizadas")
    laboratorio_origen = models.ForeignKey(
        Ambiente,
        verbose_name="Laboratorio de origen",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reparaciones",
        help_text="Laboratorio del que salió el equipo (se guarda aunque luego cambie de laboratorio).",
    )
    fecha_salida = models.DateField("Fecha de salida", default=timezone.localdate, db_index=True)
    fecha_devolucion = models.DateField("Fecha de devolución", null=True, blank=True, db_index=True)
    diagnostico = models.TextField("Diagnóstico")
    trabajo_realizado = models.TextField("Trabajo realizado", blank=True)
    repuestos_usados = models.TextField("Repuestos usados", blank=True, help_text="Escribe los repuestos que se cambiaron, uno por línea.")
    resultado = models.CharField("Resultado", max_length=16, choices=Resultado.choices, blank=True)
    observaciones = models.TextField("Observaciones", blank=True)
    uuid_cliente = models.UUIDField("UUID del cliente", null=True, blank=True, unique=True, db_index=True)
    creado_sin_conexion = models.BooleanField("Creado sin conexión", default=False)
    fecha_cliente = models.DateTimeField("Fecha del cliente", null=True, blank=True)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)
    actualizado_en = models.DateTimeField("Actualizado en", auto_now=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Creado por", null=True, blank=True, on_delete=models.SET_NULL, related_name="intervenciones_creadas")

    class Meta:
        verbose_name = "reparación"
        verbose_name_plural = "reparaciones"
        ordering = ["fecha_salida", "pk"]
        indexes = [models.Index(fields=["tecnico", "fecha_salida"], name="rep_tecnico_salida_idx")]

    def __str__(self):
        return f"Reparación #{self.pk} - {self.solicitud.equipo.codigo}"

    @property
    def equipo(self):
        return self.solicitud.equipo

    @property
    def terminada(self):
        return self.fecha_devolucion is not None

    @property
    def dias_fuera(self):
        """Días que el equipo estuvo (o lleva) fuera: devolución − salida."""
        if not self.fecha_salida:
            return None
        fin = self.fecha_devolucion or timezone.localdate()
        return (fin - self.fecha_salida).days

    def clean(self):
        errores = {}
        if self.fecha_devolucion and self.fecha_salida and self.fecha_devolucion < self.fecha_salida:
            errores["fecha_devolucion"] = "La fecha de devolución debe ser igual o posterior a la fecha de salida."
        if self.fecha_salida and self.fecha_salida > timezone.localdate():
            errores["fecha_salida"] = "La fecha de salida no puede ser futura."
        if self.fecha_devolucion and self.fecha_devolucion > timezone.localdate():
            errores["fecha_devolucion"] = "La fecha de devolución no puede ser futura."
        if self.fecha_devolucion and not self.resultado:
            errores["resultado"] = "Selecciona el resultado al registrar la devolución."
        if self.resultado and not self.fecha_devolucion:
            errores["fecha_devolucion"] = "Indica la fecha de devolución junto con el resultado."
        if errores:
            raise ValidationError(errores)
