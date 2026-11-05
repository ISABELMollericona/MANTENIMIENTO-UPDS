from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction

from apps.ubicaciones.models import Ambiente


class CategoriaEquipo(models.Model):
    nombre = models.CharField("Nombre", max_length=100, unique=True)
    descripcion = models.TextField("Descripción", blank=True)
    activo = models.BooleanField("Activo", default=True, db_index=True)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)
    actualizado_en = models.DateTimeField("Actualizado en", auto_now=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Creado por", null=True, blank=True, on_delete=models.SET_NULL, related_name="categorias_equipo_creadas")

    class Meta:
        verbose_name = "categoría de equipo"
        verbose_name_plural = "categorías de equipo"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Equipo(models.Model):
    class Estado(models.TextChoices):
        OPERATIVO = "operativo", "Operativo"
        EN_MANTENIMIENTO = "en_mantenimiento", "En mantenimiento"
        FUERA_DE_SERVICIO = "fuera_de_servicio", "Fuera de servicio"
        DADO_DE_BAJA = "dado_de_baja", "Dado de baja"

    codigo = models.CharField("Código", max_length=60, unique=True, db_index=True)
    categoria = models.ForeignKey(CategoriaEquipo, verbose_name="Categoría", on_delete=models.PROTECT, related_name="equipos")
    marca = models.CharField("Marca", max_length=100, blank=True)
    modelo = models.CharField("Modelo", max_length=100, blank=True)
    numero_serie = models.CharField("Número de serie", max_length=140, blank=True, db_index=True)
    fecha_compra = models.DateField("Fecha de compra", null=True, blank=True)
    costo_compra = models.DecimalField("Costo de compra (Bs.)", max_digits=12, decimal_places=2, null=True, blank=True)
    ambiente = models.ForeignKey(Ambiente, verbose_name="Ambiente", null=True, blank=True, on_delete=models.SET_NULL, related_name="equipos", db_index=True)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Responsable", null=True, blank=True, on_delete=models.SET_NULL, related_name="equipos_responsable")
    estado = models.CharField("Estado", max_length=24, choices=Estado.choices, default=Estado.OPERATIVO, db_index=True)
    observaciones = models.TextField("Observaciones", blank=True)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)
    actualizado_en = models.DateTimeField("Actualizado en", auto_now=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Creado por", null=True, blank=True, on_delete=models.SET_NULL, related_name="equipos_creados")

    class Meta:
        verbose_name = "equipo"
        verbose_name_plural = "equipos"
        ordering = ["codigo"]
        indexes = [
            models.Index(fields=["estado", "categoria"], name="eq_estado_cat_idx"),
            models.Index(fields=["ambiente", "estado"], name="eq_amb_estado_idx"),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.marca} {self.modelo}".strip()

    def save(self, *args, **kwargs):
        campos = ("ambiente_id", "responsable_id", "estado")
        cambios = []
        with transaction.atomic():
            if self.pk:
                anterior = type(self).objects.select_for_update(of=("self",)).select_related("ambiente", "responsable").get(pk=self.pk)
                for campo in campos:
                    valor_anterior = getattr(anterior, campo)
                    valor_nuevo = getattr(self, campo)
                    if valor_anterior != valor_nuevo:
                        if campo == "ambiente_id":
                            anterior_texto = str(anterior.ambiente) if anterior.ambiente else "Sin ambiente"
                            nuevo_texto = str(self.ambiente) if self.ambiente_id else "Sin ambiente"
                            etiqueta = "ambiente"
                        elif campo == "responsable_id":
                            anterior_texto = str(anterior.responsable) if anterior.responsable else "Sin responsable"
                            nuevo_texto = str(self.responsable) if self.responsable_id else "Sin responsable"
                            etiqueta = "responsable"
                        else:
                            anterior_texto = anterior.get_estado_display()
                            nuevo_texto = self.get_estado_display()
                            etiqueta = "estado"
                        cambios.append((etiqueta, anterior_texto, nuevo_texto))
            super().save(*args, **kwargs)
            if cambios:
                HistorialEquipo.objects.bulk_create([
                    HistorialEquipo(
                        equipo=self,
                        campo_cambiado=campo,
                        valor_anterior=anterior,
                        valor_nuevo=nuevo,
                        usuario=getattr(self, "_usuario_actualizacion", None),
                    )
                    for campo, anterior, nuevo in cambios
                ])

    def delete(self, *args, **kwargs):
        raise ValidationError("Los equipos no se eliminan; deben darse de baja cambiando su estado.")


class HistorialEquipo(models.Model):
    class Campo(models.TextChoices):
        AMBIENTE = "ambiente", "Ambiente"
        RESPONSABLE = "responsable", "Responsable"
        ESTADO = "estado", "Estado"

    equipo = models.ForeignKey(Equipo, verbose_name="Equipo", on_delete=models.PROTECT, related_name="historial")
    campo_cambiado = models.CharField("Campo cambiado", max_length=20, choices=Campo.choices)
    valor_anterior = models.CharField("Valor anterior", max_length=255)
    valor_nuevo = models.CharField("Valor nuevo", max_length=255)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Usuario", null=True, blank=True, on_delete=models.SET_NULL, related_name="cambios_equipo")
    fecha = models.DateTimeField("Fecha", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "historial de equipo"
        verbose_name_plural = "historial de equipos"
        ordering = ["-fecha", "-pk"]

    def __str__(self):
        return f"{self.equipo.codigo}: {self.get_campo_cambiado_display()}"