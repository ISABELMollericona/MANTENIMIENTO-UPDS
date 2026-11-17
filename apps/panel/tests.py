from django.contrib.auth.models import Permission
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
        # Un rol que solo ve el panel (sin permiso para leer reportes de falla).
        solo_panel = Rol.objects.create(nombre="Solo panel")
        solo_panel.grupo.permissions.add(Permission.objects.get(content_type__app_label="cuentas", codename="ver_dashboard"))
        self.autoridad = Usuario.objects.create_user(username="autoridad", password="Clave-Segura-2026!")
        self.autoridad.groups.add(solo_panel.grupo)
        self.solicitante = Usuario.objects.create_user(username="docente", password="Clave-Segura-2026!")
        self.rol_solicitante = Rol.objects.get(nombre="Jefe de carrera")
        self.solicitante.groups.add(self.rol_solicitante.grupo)
        ambiente = Ambiente.objects.create(nombre="Laboratorio", tipo="laboratorio", bloque="A")
        categoria = CategoriaEquipo.objects.create(nombre="Computadora")
        equipo = Equipo.objects.create(codigo="EQ-001", categoria=categoria, ambiente=ambiente)
        self.solicitud = Solicitud.objects.create(equipo=equipo, docente_solicitante="Lic. Rojas", descripcion="Falla privada de prueba", solicitante=self.solicitante)

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
        self.assertContains(respuesta, "no tiene un rol asignado")
        self.assertNotContains(respuesta, "EQ-001")

    def test_jefe_de_carrera_ve_atajos_y_no_indicadores(self):
        self.client.force_login(self.solicitante)
        respuesta = self.client.get(reverse("panel"))
        self.assertFalse(respuesta.context["mostrar_indicadores"])
        self.assertContains(respuesta, "Reportar una falla")
        self.assertNotContains(respuesta, "Equipos por estado")


class KeepAliveTests(TestCase):
    def test_keepalive_responde_sin_autenticacion_ni_consultas(self):
        with self.assertNumQueries(0):
            respuesta = self.client.get(reverse("keepalive"))

        self.assertEqual(respuesta.status_code, 204)
        self.assertEqual(respuesta["Cache-Control"], "no-store")

class AccesoSinSesionTests(TestCase):
    """Sin sesión se redirige al login; con sesión y sin permiso se responde 403 con la página propia."""

    rutas = ["/equipos/", "/solicitudes/", "/reportes/", "/ambientes/", "/preventivo/", "/intervenciones/mis-tareas/", "/cuentas/usuarios/", "/cuentas/roles/"]

    def test_anonimo_va_al_login_y_vuelve(self):
        for ruta in self.rutas:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 302)
                self.assertTrue(respuesta["Location"].startswith("/cuentas/ingresar/?next="))

    def test_usuario_sin_permiso_ve_403_propio(self):
        from django.contrib.auth import get_user_model

        usuario = get_user_model().objects.create_user("sinpermisos", password="Clave-Prueba-123!")
        self.client.force_login(usuario)
        for ruta in self.rutas:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 403)
                self.assertContains(respuesta, "Acceso restringido", status_code=403)


class PaginaNoEncontradaTests(TestCase):
    """Con DEBUG=False (producción) una URL inexistente muestra la página 404 propia."""

    def test_url_inexistente_muestra_404_con_estilo_upds(self):
        from django.test import override_settings

        with override_settings(DEBUG=False):
            respuesta = self.client.get("/esta-pagina-no-existe/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertContains(respuesta, "Página no encontrada", status_code=404)
        self.assertContains(respuesta, "Volver al inicio", status_code=404)

    def test_envio_sin_token_csrf_muestra_pagina_propia(self):
        from django.test import Client, override_settings

        cliente = Client(enforce_csrf_checks=True)
        with override_settings(DEBUG=False):
            respuesta = cliente.post("/cuentas/ingresar/", {"username": "x", "password": "y"})
        self.assertEqual(respuesta.status_code, 403)
        self.assertContains(respuesta, "El formulario venció", status_code=403)
