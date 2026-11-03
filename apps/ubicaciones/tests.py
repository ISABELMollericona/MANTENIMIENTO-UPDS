from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.cuentas.models import Rol, Usuario
from .models import Ambiente


class AmbientesTests(TestCase):
    def setUp(self):
        call_command("seed_roles", verbosity=0)
        self.rol = Rol.objects.get(nombre="Responsable de equipamiento")
        self.rol.grupo.permissions.add(*Permission.objects.filter(content_type__app_label="cuentas", codename__in=["ver_ambientes", "crear_ambientes", "editar_ambientes", "dar_baja_ambientes"]))
        self.usuario = Usuario.objects.create_user(username="responsable", password="Clave-Segura-2026!")
        self.usuario.groups.add(self.rol.grupo)
        self.client.force_login(self.usuario)

    def test_crear_editar_y_desactivar_ambiente_conserva_registro(self):
        response = self.client.post(reverse("ubicaciones:crear"), {"nombre": "Laboratorio de Física", "tipo": "laboratorio", "bloque": "Bloque A", "responsable": ""})
        self.assertRedirects(response, reverse("ubicaciones:lista"))
        ambiente = Ambiente.objects.get(nombre="Laboratorio de Física")
        response = self.client.post(reverse("ubicaciones:editar", args=[ambiente.pk]), {"nombre": "Laboratorio Física II", "tipo": "laboratorio", "bloque": "Bloque B", "responsable": ""})
        self.assertRedirects(response, reverse("ubicaciones:lista"))
        response = self.client.post(reverse("ubicaciones:desactivar", args=[ambiente.pk]))
        self.assertRedirects(response, reverse("ubicaciones:lista"))
        ambiente.refresh_from_db()
        self.assertFalse(ambiente.activo)
        self.assertEqual(ambiente.nombre, "Laboratorio Física II")

    def test_usuario_sin_permiso_no_puede_ver_ambientes(self):
        self.usuario.groups.clear()
        self.assertEqual(self.client.get(reverse("ubicaciones:lista")).status_code, 403)