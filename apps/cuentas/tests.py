from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .forms import RolForm, UsuarioBaseForm, UsuarioCreacionForm
from .models import AuditoriaSeguridad, Rol, Usuario


class CuentasBaseTestCase(TestCase):
    def setUp(self):
        call_command("seed_roles", verbosity=0)
        self.rol_admin = Rol.objects.get(nombre="Administrador")
        self.rol_solicitante = Rol.objects.get(nombre="Solicitante")

    def crear_usuario(self, nombre, rol=None, **datos):
        usuario = Usuario.objects.create_user(
            username=nombre,
            password="Cuenta-Segura-2026!",
            email=f"{nombre}@upds.edu.bo",
            **datos,
        )
        if rol:
            usuario.groups.add(rol.grupo)
        return usuario

    def asignar_permisos(self, rol, *codenames):
        permisos = Permission.objects.filter(content_type__app_label="cuentas", content_type__model="catalogopermiso", codename__in=codenames)
        rol.grupo.permissions.add(*permisos)


class RolesDinamicosTests(CuentasBaseTestCase):
    def test_seed_roles_es_idempotente_y_administrador_tiene_todos_los_permisos(self):
        call_command("seed_roles", verbosity=0)
        self.assertEqual(Rol.objects.count(), 5)
        self.assertEqual(self.rol_admin.grupo.permissions.count(), Permission.objects.count())
        self.assertTrue(self.rol_admin.protegido)

    def test_matriz_crea_rol_y_asigna_permisos_dinamicamente(self):
        permiso = Permission.objects.get(content_type__app_label="cuentas", codename="ver_equipos")
        datos = {"nombre": "Encargado de laboratorio", "descripcion": "Consulta equipos", "permisos": [str(permiso.pk)]}
        form = RolForm(data=datos)
        self.assertTrue(form.is_valid(), form.errors)
        rol = form.save()
        self.assertEqual(rol.grupo.name, "Encargado de laboratorio")
        self.assertTrue(rol.grupo.permissions.filter(pk=permiso.pk).exists())

    def test_rol_asignado_a_usuarios_no_se_puede_eliminar(self):
        rol = Rol.objects.get(nombre="Técnico")
        self.crear_usuario("tecnico", rol)
        with self.assertRaisesMessage(ValidationError, "No se puede eliminar un rol con usuarios asignados"):
            rol.delete()

    def test_rol_administrador_no_se_elimina_ni_pierde_permisos(self):
        permisos_antes = set(self.rol_admin.grupo.permissions.values_list("pk", flat=True))
        formulario = RolForm(data={"nombre": "Administrador", "descripcion": "Cuenta maestra actualizada", "permisos": []}, instance=self.rol_admin)
        self.assertTrue(formulario.is_valid(), formulario.errors)
        formulario.save()
        self.rol_admin.refresh_from_db()
        self.assertEqual(set(self.rol_admin.grupo.permissions.values_list("pk", flat=True)), permisos_antes)
        with self.assertRaisesMessage(ValidationError, "El rol Administrador no se puede eliminar"):
            self.rol_admin.delete()
        with self.assertRaisesMessage(ValidationError, "El nombre del rol Administrador está protegido"):
            self.rol_admin.nombre = "Otro nombre"
            self.rol_admin.save()

    def test_seed_roles_no_sobrescribe_permisos_personalizados(self):
        rol = Rol.objects.get(nombre="Técnico")
        permiso = Permission.objects.get(content_type__app_label="cuentas", codename="ver_reportes")
        rol.grupo.permissions.add(permiso)
        call_command("seed_roles", verbosity=0)
        self.assertTrue(rol.grupo.permissions.filter(pk=permiso.pk).exists())


class UsuariosYProteccionesTests(CuentasBaseTestCase):
    def test_formulario_crea_usuario_con_contrasena_cifrada_y_roles(self):
        datos = {
            "username": "docente",
            "first_name": "Ana",
            "last_name": "Paz",
            "email": "ana@upds.edu.bo",
            "is_active": "on",
            "force_password_change": "on",
            "grupos": [str(self.rol_solicitante.grupo_id)],
            "password1": "Docente-Muy-Segura-2026!",
            "password2": "Docente-Muy-Segura-2026!",
        }
        form = UsuarioCreacionForm(data=datos)
        self.assertTrue(form.is_valid(), form.errors)
        usuario = form.save()
        self.assertTrue(usuario.check_password(datos["password1"]))
        self.assertTrue(usuario.force_password_change)
        self.assertEqual(list(usuario.groups.all()), [self.rol_solicitante.grupo])

    def test_no_se_puede_quitar_o_desactivar_al_ultimo_administrador(self):
        administrador = self.crear_usuario("admin", self.rol_admin, is_staff=True)
        datos = {
            "username": administrador.username,
            "first_name": "",
            "last_name": "",
            "email": administrador.email,
            "force_password_change": "",
            "is_active": "",
            "grupos": [],
        }
        formulario = UsuarioBaseForm(data=datos, instance=administrador)
        self.assertFalse(formulario.is_valid())
        self.assertIn("No se puede quitar el rol ni desactivar al último administrador activo.", str(formulario.errors))

    def test_cambio_forzado_de_contrasena_redirige_y_deja_acceder_al_formulario(self):
        usuario = self.crear_usuario("temporal", force_password_change=True)
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse("panel"))
        self.assertRedirects(respuesta, reverse("password_change"))
        respuesta = self.client.get(reverse("password_change"))
        self.assertEqual(respuesta.status_code, 200)

    def test_cambio_de_contrasena_limpia_el_requisito_obligatorio(self):
        usuario = self.crear_usuario("temporal", force_password_change=True)
        self.client.force_login(usuario)
        respuesta = self.client.post(
            reverse("password_change"),
            {
                "old_password": "Cuenta-Segura-2026!",
                "new_password1": "Nueva-Clave-Segura-2026!",
                "new_password2": "Nueva-Clave-Segura-2026!",
            },
        )
        self.assertRedirects(respuesta, reverse("password_change_done"))
        usuario.refresh_from_db()
        self.assertFalse(usuario.force_password_change)
        self.assertEqual(self.client.get(reverse("panel")).status_code, 200)

    def test_asignar_rol_a_usuario_se_audita(self):
        rol_gestor = Rol.objects.get(nombre="Responsable de equipamiento")
        self.asignar_permisos(rol_gestor, "ver_usuarios", "editar_usuarios", "gestionar_usuarios")
        gestor = self.crear_usuario("gestor", rol_gestor)
        usuario = self.crear_usuario("docente")
        self.client.force_login(gestor)
        respuesta = self.client.post(
            reverse("cuentas:usuario_editar", args=[usuario.pk]),
            {
                "username": usuario.username,
                "first_name": "",
                "last_name": "",
                "email": usuario.email,
                "is_active": "on",
                "force_password_change": "",
                "grupos": [str(self.rol_solicitante.grupo_id)],
            },
        )
        self.assertRedirects(respuesta, reverse("cuentas:usuarios"))
        usuario.refresh_from_db()
        self.assertIn(self.rol_solicitante.grupo, usuario.groups.all())
        evento = AuditoriaSeguridad.objects.get(accion="usuario_actualizado")
        self.assertEqual(evento.usuario, gestor)
        self.assertIn("Solicitante", evento.detalle)


class VistasRolesTests(CuentasBaseTestCase):
    def test_usuario_sin_permiso_recibe_403(self):
        usuario = self.crear_usuario("sinpermisos")
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse("cuentas:roles"))
        self.assertEqual(respuesta.status_code, 403)

    def test_usuario_con_permiso_ve_matriz_y_crea_rol_con_auditoria(self):
        rol_gestor = Rol.objects.get(nombre="Responsable de equipamiento")
        self.asignar_permisos(rol_gestor, "ver_roles", "crear_roles", "gestionar_roles")
        gestor = self.crear_usuario("gestor_roles", rol_gestor)
        self.client.force_login(gestor)
        respuesta = self.client.get(reverse("cuentas:roles"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Roles y permisos")
        self.assertContains(respuesta, "Administrador")

        permiso = Permission.objects.get(content_type__app_label="cuentas", codename="ver_equipos")
        respuesta = self.client.post(
            reverse("cuentas:rol_crear"),
            {"nombre": "Consulta de equipos", "descripcion": "Solo consulta", "permisos": [str(permiso.pk)]},
        )
        self.assertRedirects(respuesta, reverse("cuentas:roles"))
        nuevo_rol = Rol.objects.get(nombre="Consulta de equipos")
        self.assertTrue(nuevo_rol.grupo.permissions.filter(pk=permiso.pk).exists())
        evento = AuditoriaSeguridad.objects.get(accion="rol_creado")
        self.assertEqual(evento.usuario, gestor)
        self.assertIn("ver_equipos", evento.detalle)

    def test_asignar_permisos_a_un_rol_se_aplica_al_siguiente_acceso(self):
        rol = Rol.objects.get(nombre="Técnico")
        tecnico = self.crear_usuario("tecnico", rol)
        url = reverse("cuentas:roles")
        self.client.force_login(tecnico)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.asignar_permisos(rol, "ver_roles")
        self.client.logout()
        self.client.force_login(tecnico)
        self.assertEqual(self.client.get(url).status_code, 200)


class SeedDemoCommandTests(TestCase):
    def test_seed_demo_es_idempotente_y_crea_volumen_solicitado(self):
        import os

        from django.contrib.auth import get_user_model
        from django.core.management import call_command
        from django.utils import timezone

        from apps.cuentas.management.commands.seed_demo import AMBIENTES
        from apps.equipos.models import Equipo
        from apps.intervenciones.models import Intervencion, RepuestoUsado
        from apps.preventivo.models import MantenimientoProgramado, PlanPreventivo
        from apps.solicitudes.models import Solicitud
        from apps.ubicaciones.models import Ambiente

        call_command("seed_demo", verbosity=0)
        password = os.getenv("DEMO_PASSWORD", "Demo-UPDS-2026!")
        administrador = get_user_model().objects.get(username="admin.demo")
        self.assertTrue(administrador.is_superuser)
        self.assertTrue(administrador.check_password(password))
        self.assertTrue(administrador.force_password_change)
        self.assertEqual(Ambiente.objects.filter(nombre__in=[nombre for nombre, _, _ in AMBIENTES]).count(), 8)
        self.assertEqual(Equipo.objects.filter(codigo__startswith="DEMO-").count(), 40)
        self.assertEqual(Solicitud.objects.filter(descripcion__startswith="Solicitud ficticia").count(), 25)
        self.assertGreater(Intervencion.objects.count(), 0)
        self.assertGreater(RepuestoUsado.objects.count(), 0)
        self.assertGreater(PlanPreventivo.objects.count(), 0)
        self.assertTrue(MantenimientoProgramado.objects.filter(fecha_programada__lt=timezone.localdate(), estado="pendiente").exists())

        conteos_antes = (
            Ambiente.objects.count(), Equipo.objects.count(), Solicitud.objects.count(),
            Intervencion.objects.count(), MantenimientoProgramado.objects.count(),
        )
        call_command("seed_demo", verbosity=0)
        conteos_despues = (
            Ambiente.objects.count(), Equipo.objects.count(), Solicitud.objects.count(),
            Intervencion.objects.count(), MantenimientoProgramado.objects.count(),
        )
        self.assertEqual(conteos_despues, conteos_antes)
