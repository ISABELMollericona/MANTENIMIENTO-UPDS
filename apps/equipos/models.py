from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction

from apps.ubicaciones.models import Ambiente


class CategoriaEquipo(models.Model):
    nombre = models.CharField("Nombre", max_length=100, unique=True)
    descripcion = models.TextField("Descripción", blank=True)
    es_periferico = models.BooleanField(
        "Es periférico",
        default=False,
        help_text="Márcalo para teclados, mouse y otros periféricos que se asocian a una computadora.",
    )
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


class EstadoEquipo(models.Model):
    """Estados de equipo editables desde el sistema.

    El nombre visible se puede cambiar libremente (el cliente aún debe aprobarlos).
    El ``tipo`` indica al sistema cómo tratar cada estado: el equipo está disponible,
    está fuera por reparación o está retirado (baja).
    """

    class Tipo(models.TextChoices):
        OPERATIVO = "operativo", "Disponible (operativo)"
        REPARACION = "reparacion", "Fuera por mantenimiento o reparación"
        BAJA = "baja", "Retirado (obsoleto o dado de baja)"

    nombre = models.CharField("Nombre", max_length=80, unique=True)
    tipo = models.CharField("Comportamiento en el sistema", max_length=12, choices=Tipo.choices, db_index=True)
    orden = models.PositiveSmallIntegerField("Orden", default=0)
    activo = models.BooleanField("Activo", default=True, db_index=True)

    class Meta:
        verbose_name = "estado de equipo"
        verbose_name_plural = "estados de equipo"
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre

    @classmethod
    def del_tipo(cls, tipo):
        """Primer estado activo de un tipo (por ejemplo, el estado operativo por defecto)."""
        estado = cls.objects.filter(tipo=tipo, activo=True).order_by("orden", "pk").first()
        if estado is None:
            raise ValidationError(f"No hay un estado activo de tipo «{cls.Tipo(tipo).label}». Créalo en Equipos › Estados.")
        return estado

    def delete(self, *args, **kwargs):
        if self.equipos.exists():
            raise ValidationError("No se puede eliminar un estado que tienen equipos; desactívalo.")
        return super().delete(*args, **kwargs)


def estado_operativo_por_defecto():
    estado = EstadoEquipo.objects.filter(tipo=EstadoEquipo.Tipo.OPERATIVO, activo=True).order_by("orden", "pk").first()
    return estado.pk if estado else None


class Equipo(models.Model):
    codigo = models.CharField("Código de inventario", max_length=60, unique=True, db_index=True)
    categoria = models.ForeignKey(CategoriaEquipo, verbose_name="Categoría", on_delete=models.PROTECT, related_name="equipos")
    marca = models.CharField("Marca", max_length=100, blank=True)
    modelo = models.CharField("Modelo", max_length=100, blank=True)
    numero_serie = models.CharField("Número de serie", max_length=140, blank=True, db_index=True)
    fecha_compra = models.DateField("Fecha de compra", null=True, blank=True)
    ambiente = models.ForeignKey(Ambiente, verbose_name="Laboratorio", null=True, blank=True, on_delete=models.SET_NULL, related_name="equipos", db_index=True)
    equipo_principal = models.ForeignKey(
        "self",
        verbose_name="Computadora asociada",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="perifericos",
        help_text="Solo para periféricos (teclado, mouse): la computadora a la que pertenecen.",
    )
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Responsable", null=True, blank=True, on_delete=models.SET_NULL, related_name="equipos_responsable")
    estado = models.ForeignKey(EstadoEquipo, verbose_name="Estado", on_delete=models.PROTECT, related_name="equipos", default=estado_operativo_por_defecto)
    observaciones = models.TextField("Observaciones", blank=True)
    # Baja: el sistema solo registra el retiro y si se informó a Vicerrectoría.
    # La baja oficial la realiza Vicerrectoría Administrativa fuera del sistema.
    fecha_baja = models.DateField("Fecha de retiro", null=True, blank=True)
    motivo_baja = models.TextField("Motivo del retiro", blank=True)
    informado_vicerrectoria = models.BooleanField("Informado a Vicerrectoría Administrativa", default=False)
    fecha_informe_vicerrectoria = models.DateField("Fecha en que se informó a Vicerrectoría", null=True, blank=True)
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

    @property
    def es_periferico(self):
        return bool(self.categoria_id and self.categoria.es_periferico)

    @property
    def esta_de_baja(self):
        return bool(self.estado_id and self.estado.tipo == EstadoEquipo.Tipo.BAJA)

    @property
    def esta_en_reparacion(self):
        return bool(self.estado_id and self.estado.tipo == EstadoEquipo.Tipo.REPARACION)

    @property
    def esta_operativo(self):
        return bool(self.estado_id and self.estado.tipo == EstadoEquipo.Tipo.OPERATIVO)

    @property
    def etiqueta_completa(self):
        """Texto para listas desplegables: indica a qué computadora pertenece un periférico."""
        texto = str(self)
        if self.equipo_principal_id:
            texto += f" (periférico de {self.equipo_principal.codigo})"
        return texto

    def clean(self):
        errores = {}
        if self.equipo_principal_id:
            if self.pk and self.equipo_principal_id == self.pk:
                errores["equipo_principal"] = "Un equipo no puede ser periférico de sí mismo."
            elif self.categoria_id and not self.categoria.es_periferico:
                errores["equipo_principal"] = "Solo los periféricos (teclado, mouse) se asocian a una computadora. Revisa la categoría."
            elif self.equipo_principal.es_periferico:
                errores["equipo_principal"] = "Elige una computadora, no otro periférico."
        if self.fecha_informe_vicerrectoria and not self.informado_vicerrectoria:
            errores["informado_vicerrectoria"] = "Marca «Informado a Vicerrectoría» si indicas la fecha del informe."
        if self.informado_vicerrectoria and not self.fecha_informe_vicerrectoria:
            errores["fecha_informe_vicerrectoria"] = "Indica la fecha en que se informó a Vicerrectoría."
        if self.fecha_baja and self.fecha_informe_vicerrectoria and self.fecha_informe_vicerrectoria < self.fecha_baja:
            errores["fecha_informe_vicerrectoria"] = "La fecha del informe no puede ser anterior a la fecha de retiro."
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        campos = ("ambiente_id", "responsable_id", "estado_id", "informado_vicerrectoria")
        cambios = []
        with transaction.atomic():
            if self.pk:
                anterior = type(self).objects.select_for_update(of=("self",)).select_related("ambiente", "responsable", "estado").get(pk=self.pk)
                for campo in campos:
                    valor_anterior = getattr(anterior, campo)
                    valor_nuevo = getattr(self, campo)
                    if valor_anterior == valor_nuevo:
                        continue
                    if campo == "ambiente_id":
                        anterior_texto = str(anterior.ambiente) if anterior.ambiente else "Sin laboratorio"
                        nuevo_texto = str(self.ambiente) if self.ambiente_id else "Sin laboratorio"
                        etiqueta = HistorialEquipo.Campo.AMBIENTE
                    elif campo == "responsable_id":
                        anterior_texto = str(anterior.responsable) if anterior.responsable else "Sin responsable"
                        nuevo_texto = str(self.responsable) if self.responsable_id else "Sin responsable"
                        etiqueta = HistorialEquipo.Campo.RESPONSABLE
                    elif campo == "estado_id":
                        anterior_texto = str(anterior.estado)
                        nuevo_texto = str(self.estado)
                        etiqueta = HistorialEquipo.Campo.ESTADO
                    else:
                        anterior_texto = "Sí" if anterior.informado_vicerrectoria else "No"
                        nuevo_texto = "Sí" if self.informado_vicerrectoria else "No"
                        if self.informado_vicerrectoria and self.fecha_informe_vicerrectoria:
                            nuevo_texto += f" ({self.fecha_informe_vicerrectoria:%d/%m/%Y})"
                        etiqueta = HistorialEquipo.Campo.VICERRECTORIA
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
        AMBIENTE = "ambiente", "Laboratorio"
        RESPONSABLE = "responsable", "Responsable"
        ESTADO = "estado", "Estado"
        VICERRECTORIA = "vicerrectoria", "Informado a Vicerrectoría"

    equipo = models.ForeignKey(Equipo, verbose_name="Equipo", on_delete=models.PROTECT, related_name="historial")
    campo_cambiado = models.CharField("Campo cambiado", max_length=20, choices=Campo.choices)
    valor_anterior = models.CharField("Valor anterior", max_length=255)
    valor_nuevo = models.CharField("Valor nuevo", max_length=255)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Cambiado por", null=True, blank=True, on_delete=models.SET_NULL, related_name="cambios_equipo")
    fecha = models.DateTimeField("Fecha", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "historial de equipo"
        verbose_name_plural = "historial de equipos"
        ordering = ["-fecha", "-pk"]

    def __str__(self):
        return f"{self.equipo.codigo}: {self.get_campo_cambiado_display()}"
