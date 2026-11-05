from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.cuentas.models import Rol, Usuario
from apps.equipos.models import CategoriaEquipo, Equipo
from apps.solicitudes.models import Solicitud
from apps.ubicaciones.models import Ambiente


class PanelInicioTests(TestCase):
    def setUp(self):
        call_command("seed_roles", verbosity=0)
        self.rol_autoridad = Rol.objects.get(nombre="Autoridad")
        self.autoridad = Usuario.objects.create_user(username="autoridad", password="Clave-Segura-2026!")
        self.autoridad.groups.add(self.rol_autoridad.grupo)
        self.solicitante = Usuario.objects.create_user(username="docente", password="Clave-Segura-2026!")
        self.rol_solicitante = Rol.objects.get(nombre="Solicitante")
        self.solicitante.groups.add(self.rol_solicitante.grupo)
        ambiente = Ambiente.objects.create(nombre="Laboratorio", tipo="laboratorio", bloque="A")
        categoria = CategoriaEquipo.objects.create(nombre="Computadora")
        equipo = Equipo.objects.create(codigo="EQ-001", categoria=categoria, ambiente=ambiente)
        self.solicitud = Solicitud.objects.create(equipo=equipo, descripcion="Falla privada de prueba", solicitante=self.solicitante)

    def test_usuario_con_permiso_dashboard_ve_resumen_y_grafico(self):
        self.client.force_login(self.autoridad)
        respuesta = self.client.get(reverse("panel"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Panel de inicio")
        self.assertContains(respuesta, "Equipos por estado")
        self.assertEqual(respuesta.context["total_equipos"], 1)

    def test_dashboard_no_expone_solicitudes_sin_permiso_de_lectura(self):
        self.client.force_login(self.autoridad)
        respuesta = self.client.get(reverse("panel"))
        self.assertNotContains(respuesta, self.solicitud.descripcion)

    def test_usuario_sin_permiso_de_dashboard_no_ve_indicadores(self):
        usuario = Usuario.objects.create_user(username="sin_panel", password="Clave-Segura-2026!")
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse("panel"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "no tiene permiso para ver los indicadores")
        self.assertNotContains(respuesta, "EQ-001")


class KeepAliveTests(TestCase):
    def test_keepalive_responde_sin_autenticacion_ni_consultas(self):
        with self.assertNumQueries(0):
            respuesta = self.client.get(reverse("keepalive"))

        self.assertEqual(respuesta.status_code, 204)
        self.assertEqual(respuesta["Cache-Control"], "no-store")