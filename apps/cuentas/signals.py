from django.contrib.auth.models import Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def mantener_permisos_de_administrador(sender, **kwargs):
    if sender.label != "cuentas":
        return
    from .models import Rol

    rol = Rol.objects.filter(protegido=True, nombre="Administrador").first()
    if rol:
        rol.grupo.permissions.set(Permission.objects.all())
