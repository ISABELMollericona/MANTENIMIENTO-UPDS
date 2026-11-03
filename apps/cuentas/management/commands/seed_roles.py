from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cuentas.models import Rol

ROLES_INICIALES = {
    "Administrador": {
        "descripcion": "Acceso total a usuarios, roles, permisos y todos los módulos.",
        "permisos": "*",
        "protegido": True,
    },
    "Responsable de equipamiento": {
        "descripcion": "Gestiona ambientes y equipos, coordina solicitudes, técnicos, preventivos y reportes.",
        "permisos": [
            "ver_dashboard", "ver_ambientes", "crear_ambientes", "editar_ambientes", "dar_baja_ambientes",
            "ver_equipos", "crear_equipos", "editar_equipos", "dar_baja_equipos", "exportar_equipos", "autorizar_baja_equipo",
            "ver_solicitudes", "crear_solicitudes", "editar_solicitudes", "cancelar_solicitudes", "ver_todas_solicitudes",
            "asignar_tecnico", "cambiar_estado_solicitud", "reabrir_solicitud", "ver_intervenciones", "ver_preventivos", "crear_preventivos",
            "editar_preventivos", "ver_reportes", "exportar_reportes",
        ],
    },
    "Técnico": {
        "descripcion": "Atiende solicitudes asignadas, registra intervenciones y actualiza sus estados.",
        "permisos": ["ver_dashboard", "ver_solicitudes", "ver_intervenciones", "crear_intervenciones", "editar_intervenciones", "cambiar_estado_solicitud"],
    },
    "Solicitante": {
        "descripcion": "Registra solicitudes y consulta únicamente las que reportó.",
        "permisos": ["ver_dashboard", "ver_solicitudes", "crear_solicitudes"],
    },
    "Autoridad": {
        "descripcion": "Consulta el panel de inicio y los reportes del sistema.",
        "permisos": ["ver_dashboard", "ver_reportes", "exportar_reportes"],
    },
}


class Command(BaseCommand):
    help = "Crea los roles iniciales del sistema sin duplicarlos."

    @transaction.atomic
    def handle(self, *args, **options):
        catalogo = Permission.objects.filter(content_type__app_label="cuentas", content_type__model="catalogopermiso")
        for nombre, configuracion in ROLES_INICIALES.items():
            grupo, _ = Group.objects.get_or_create(name=nombre)
            rol, creado = Rol.objects.get_or_create(
                nombre=nombre,
                defaults={"grupo": grupo, "descripcion": configuracion["descripcion"], "protegido": configuracion.get("protegido", False)},
            )
            if rol.grupo_id != grupo.pk:
                rol.grupo = grupo
                rol.save(update_fields=["grupo"])
            if configuracion.get("protegido") and not rol.protegido:
                rol.protegido = True
                rol.save(update_fields=["protegido"])
            if configuracion["permisos"] == "*":
                grupo.permissions.set(Permission.objects.all())
            elif creado:
                codenames = configuracion["permisos"]
                grupo.permissions.add(*catalogo.filter(codename__in=codenames))
            self.stdout.write(f"{'Creado' if creado else 'Verificado'}: {nombre}")

        grupo_admin = Group.objects.get(name="Administrador")
        usuario = get_user_model()
        for administrador in usuario.objects.filter(is_superuser=True):
            administrador.groups.add(grupo_admin)

        self.stdout.write(self.style.SUCCESS("Roles iniciales listos. Puedes editarlos desde la pantalla Roles y permisos."))
