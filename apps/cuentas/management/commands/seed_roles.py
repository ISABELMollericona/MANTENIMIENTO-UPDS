from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cuentas.models import Rol

# Roles acordados con el cliente. Los docentes NO tienen cuenta: el jefe de carrera
# registra los reportes de falla en su nombre.
ROLES_INICIALES = {
    "Administrador": {
        "descripcion": "Administrador del sistema: crea usuarios y asigna roles. Tiene acceso total.",
        "permisos": "*",
        "protegido": True,
    },
    "Responsable de mantenimiento": {
        "descripcion": "Registra equipos, recibe los reportes de falla, asigna reparaciones a técnicos, carga el cronograma preventivo, marca las bajas informadas a Vicerrectoría y ve reportes.",
        "permisos": [
            "ver_dashboard",
            "ver_ambientes", "crear_ambientes", "editar_ambientes", "dar_baja_ambientes",
            "ver_equipos", "crear_equipos", "editar_equipos", "dar_baja_equipos", "exportar_equipos", "autorizar_baja_equipo",
            "ver_solicitudes", "ver_todas_solicitudes", "cancelar_solicitudes", "asignar_tecnico", "cambiar_estado_solicitud", "reabrir_solicitud",
            "ver_preventivos", "crear_preventivos", "editar_preventivos",
            "ver_reportes", "exportar_reportes",
        ],
    },
    "Técnico": {
        "descripcion": "Pasante o becario: ve solo sus reparaciones y mantenimientos asignados y registra el trabajo realizado y los repuestos usados.",
        "permisos": [
            "ver_solicitudes", "cambiar_estado_solicitud",
            "ver_intervenciones", "crear_intervenciones", "editar_intervenciones",
            "ver_preventivos", "editar_preventivos",
        ],
    },
    "Jefe de carrera": {
        "descripcion": "Registra reportes de falla en nombre de los docentes de su carrera y consulta los que registró.",
        "permisos": ["ver_solicitudes", "crear_solicitudes", "cancelar_solicitudes"],
    },
    "Estudiante": {
        "descripcion": "Acceso muy limitado: solo consulta el estado de los equipos. No registra ni modifica nada.",
        "permisos": ["ver_equipos"],
    },
}

# Nombres usados en versiones anteriores del sistema -> nombre actual.
ROLES_RENOMBRADOS = {
    "Responsable de equipamiento": "Responsable de mantenimiento",
    "Solicitante": "Jefe de carrera",
}


class Command(BaseCommand):
    help = "Crea los roles del sistema sin duplicarlos. Con --actualizar-permisos deja cada rol con sus permisos acordados."

    def add_arguments(self, parser):
        parser.add_argument(
            "--actualizar-permisos",
            action="store_true",
            help="Reemplaza los permisos de los roles del sistema por los acordados (pierde los cambios hechos a mano en esos roles).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        actualizar = options.get("actualizar_permisos", False)
        catalogo = Permission.objects.filter(content_type__app_label="cuentas", content_type__model="catalogopermiso")

        for anterior, nuevo in ROLES_RENOMBRADOS.items():
            rol_anterior = Rol.objects.filter(nombre=anterior).first()
            if rol_anterior and not Rol.objects.filter(nombre=nuevo).exists():
                rol_anterior.nombre = nuevo
                rol_anterior.descripcion = ROLES_INICIALES[nuevo]["descripcion"]
                rol_anterior.save()
                self.stdout.write(f"Renombrado: {anterior} -> {nuevo}")

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
            elif creado or actualizar:
                grupo.permissions.set(catalogo.filter(codename__in=configuracion["permisos"]))
                if actualizar and not creado:
                    rol.descripcion = configuracion["descripcion"]
                    rol.save(update_fields=["descripcion"])
            self.stdout.write(f"{'Creado' if creado else 'Verificado'}: {nombre}")

        grupo_admin = Group.objects.get(name="Administrador")
        usuario = get_user_model()
        for administrador in usuario.objects.filter(is_superuser=True):
            administrador.groups.add(grupo_admin)

        sobrantes = Rol.objects.exclude(nombre__in=ROLES_INICIALES).values_list("nombre", flat=True)
        if sobrantes:
            self.stdout.write(self.style.WARNING(
                "Roles que no forman parte del acuerdo con el cliente (no se tocan): " + ", ".join(sobrantes)
            ))
        self.stdout.write(self.style.SUCCESS("Roles listos. Puedes editarlos desde la pantalla Roles y permisos."))
