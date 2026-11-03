from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError

from .models import Usuario

NOMBRE_ROL_ADMIN = "Administrador"


def es_administrador(usuario):
    return usuario.is_authenticated and (usuario.is_superuser or usuario.groups.filter(rol_sistema__protegido=True).exists())


def validar_roles_y_estado(usuario, grupos, activo):
    grupo_admin = Group.objects.filter(rol_sistema__protegido=True, name=NOMBRE_ROL_ADMIN).first()
    if not grupo_admin:
        return
    mantiene_admin = activo and grupo_admin in grupos
    if usuario.pk and usuario.is_active and usuario.groups.filter(pk=grupo_admin.pk).exists() and not mantiene_admin:
        administradores_activos = Usuario.objects.filter(is_active=True, groups=grupo_admin).distinct().count()
        if administradores_activos <= 1:
            raise ValidationError("No se puede quitar el rol ni desactivar al último administrador activo.")


def registrar_auditoria(request, accion, detalle):
    from .models import AuditoriaSeguridad

    usuario = request.user if request.user.is_authenticated else None
    return AuditoriaSeguridad.objects.create(
        usuario=usuario,
        accion=accion,
        detalle=detalle,
        ip=request.META.get("REMOTE_ADDR"),
    )
