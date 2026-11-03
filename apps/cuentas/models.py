from django.contrib.auth.models import AbstractUser, Group
from django.core.exceptions import ValidationError
from django.db import models, transaction


class Usuario(AbstractUser):
    force_password_change = models.BooleanField("Debe cambiar su contraseña", default=False)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)
    actualizado_en = models.DateTimeField("Actualizado en", auto_now=True)
    creado_por = models.ForeignKey("self", verbose_name="Creado por", null=True, blank=True, on_delete=models.SET_NULL, related_name="usuarios_creados")

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["last_name", "first_name", "username"]

    def __str__(self):
        return self.get_full_name() or self.username


class Rol(models.Model):
    grupo = models.OneToOneField(Group, verbose_name="Grupo de Django", on_delete=models.PROTECT, related_name="rol_sistema")
    nombre = models.CharField("Nombre", max_length=150, unique=True)
    descripcion = models.TextField("Descripción", blank=True)
    protegido = models.BooleanField("Rol protegido", default=False)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)
    actualizado_en = models.DateTimeField("Actualizado en", auto_now=True)

    class Meta:
        verbose_name = "rol"
        verbose_name_plural = "roles"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.pk and self.protegido:
                anterior = type(self).objects.get(pk=self.pk)
                if anterior.nombre != self.nombre:
                    raise ValidationError("El nombre del rol Administrador está protegido.")
            if self.grupo_id:
                self.grupo.name = self.nombre
                self.grupo.save(update_fields=["name"])
            else:
                self.grupo = Group.objects.create(name=self.nombre)
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.protegido:
            raise ValidationError("El rol Administrador no se puede eliminar.")
        if self.grupo.user_set.exists():
            raise ValidationError("No se puede eliminar un rol con usuarios asignados.")
        grupo = self.grupo
        with transaction.atomic():
            resultado = super().delete(*args, **kwargs)
            grupo.delete()
        return resultado


class CatalogoPermiso(models.Model):
    clave = models.CharField("Clave", max_length=40, default="sistema", unique=True, editable=False)

    class Meta:
        verbose_name = "catálogo de permisos"
        verbose_name_plural = "catálogo de permisos"
        default_permissions = ()
        permissions = [
            ("ver_usuarios", "Usuarios: ver"),
            ("crear_usuarios", "Usuarios: crear"),
            ("editar_usuarios", "Usuarios: editar"),
            ("desactivar_usuarios", "Usuarios: desactivar"),
            ("ver_roles", "Roles: ver"),
            ("crear_roles", "Roles: crear"),
            ("editar_roles", "Roles: editar"),
            ("eliminar_roles", "Roles: eliminar"),
            ("ver_ambientes", "Ambientes: ver"),
            ("crear_ambientes", "Ambientes: crear"),
            ("editar_ambientes", "Ambientes: editar"),
            ("dar_baja_ambientes", "Ambientes: dar de baja"),
            ("ver_equipos", "Equipos: ver"),
            ("crear_equipos", "Equipos: crear"),
            ("editar_equipos", "Equipos: editar"),
            ("dar_baja_equipos", "Equipos: dar de baja"),
            ("exportar_equipos", "Equipos: exportar"),
            ("ver_solicitudes", "Solicitudes: ver"),
            ("crear_solicitudes", "Solicitudes: crear"),
            ("editar_solicitudes", "Solicitudes: editar"),
            ("cancelar_solicitudes", "Solicitudes: cancelar"),
            ("ver_intervenciones", "Intervenciones: ver"),
            ("crear_intervenciones", "Intervenciones: crear"),
            ("editar_intervenciones", "Intervenciones: editar"),
            ("ver_preventivos", "Mantenimiento preventivo: ver"),
            ("crear_preventivos", "Mantenimiento preventivo: crear"),
            ("editar_preventivos", "Mantenimiento preventivo: editar"),
            ("ver_reportes", "Reportes: ver"),
            ("exportar_reportes", "Reportes: exportar"),
            ("ver_dashboard", "Panel de inicio: ver"),
            ("gestionar_usuarios", "Gestionar usuarios y asignar roles"),
            ("gestionar_roles", "Gestionar roles y permisos"),
            ("asignar_tecnico", "Asignar técnicos a solicitudes"),
            ("cambiar_estado_solicitud", "Cambiar estado de solicitudes asignadas"),
            ("autorizar_baja_equipo", "Autorizar la baja de equipos"),
            ("ver_todas_solicitudes", "Ver todas las solicitudes"),
        ]


class AuditoriaSeguridad(models.Model):
    usuario = models.ForeignKey("cuentas.Usuario", verbose_name="Usuario", null=True, blank=True, on_delete=models.SET_NULL, related_name="eventos_seguridad")
    accion = models.CharField("Acción", max_length=80, db_index=True)
    detalle = models.TextField("Detalle")
    fecha = models.DateTimeField("Fecha", auto_now_add=True, db_index=True)
    ip = models.GenericIPAddressField("Dirección IP", null=True, blank=True)

    class Meta:
        verbose_name = "registro de auditoría de seguridad"
        verbose_name_plural = "registros de auditoría de seguridad"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.accion} ({self.fecha:%Y-%m-%d %H:%M})"
