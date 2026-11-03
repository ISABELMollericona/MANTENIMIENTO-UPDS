from datetime import date

from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.cuentas.models import Rol, Usuario
from apps.ubicaciones.models import Ambiente
from .models import CategoriaEquipo, Equipo


class EquiposTests(TestCase):
    def setUp(self):
        call_command("seed_roles", verbosity=0)
        self.rol = Rol.objects.get(nombre="Responsable de equipamiento")
        self.rol.grupo.permissions.add(*Permission.objects.filter(content_type__app_label="cuentas", codename__in=["ver_equipos", "crear_equipos", "editar_equipos", "dar_baja_equipos", "autorizar_baja_equipo"]))
        self.usuario = Usuario.objects.create_user(username="gestor", password="Clave-Segura-2026!")
        self.usuario.groups.add(self.rol.grupo)
        self.ambiente = Ambiente.objects.create(nombre="Laboratorio", tipo="laboratorio", bloque="A")
        self.categoria = CategoriaEquipo.objects.create(nombre="Computadora")
        self.equipo = Equipo.objects.create(codigo="EQ-001", categoria=self.categoria, ambiente=self.ambiente, creado_por=self.usuario)
        self.client.force_login(self.usuario)

    def test_cambiar_ambiente_responsable_y_estado_genera_historial(self):
        segundo = Ambiente.objects.create(nombre="Aula 1", tipo="aula", bloque="B")
        responsable = Usuario.objects.create_user(username="docente", password="Clave-Segura-2026!")
        self.equipo.ambiente = segundo
        self.equipo.responsable = responsable
        self.equipo.estado = Equipo.Estado.EN_MANTENIMIENTO
        self.equipo._usuario_actualizacion = self.usuario
        self.equipo.save()
        cambios = list(self.equipo.historial.order_by("campo_cambiado").values_list("campo_cambiado", "usuario__username"))
        self.assertEqual({campo for campo, _ in cambios}, {"ambiente", "responsable", "estado"})
        self.assertTrue(all(usuario == "gestor" for _, usuario in cambios))
        self.assertEqual(self.equipo.historial.get(campo_cambiado="ambiente").valor_anterior, str(self.ambiente))

    def test_lista_filtra_por_busqueda_estado_ambiente_y_pagina_ficha(self):
        self.equipo.marca = "Dell"
        self.equipo.modelo = "OptiPlex"
        self.equipo.fecha_compra = date(2024, 1, 15)
        self.equipo.save()
        response = self.client.get(reverse("equipos:lista"), {"q": "OptiPlex", "ambiente": self.ambiente.pk, "estado": "operativo"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EQ-001")
        self.assertEqual(self.client.get(reverse("equipos:ficha", args=[self.equipo.pk])).status_code, 200)

    def test_baja_logica_exige_permiso_y_conserva_historial(self):
        response = self.client.post(reverse("equipos:baja", args=[self.equipo.pk]))
        self.assertRedirects(response, reverse("equipos:ficha", args=[self.equipo.pk]))
        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.estado, Equipo.Estado.DADO_DE_BAJA)
        self.assertEqual(self.equipo.historial.count(), 1)

    def test_sin_permiso_autorizacion_no_puede_dar_baja(self):
        self.rol.grupo.permissions.remove(Permission.objects.get(content_type__app_label="cuentas", codename="autorizar_baja_equipo"))
        response = self.client.post(reverse("equipos:baja", args=[self.equipo.pk]))
        self.assertEqual(response.status_code, 403)

    def test_edicion_normal_no_puede_evitar_el_permiso_de_baja(self):
        self.rol.grupo.permissions.remove(Permission.objects.get(content_type__app_label="cuentas", codename="autorizar_baja_equipo"))
        response = self.client.post(
            reverse("equipos:editar", args=[self.equipo.pk]),
            {
                "codigo": self.equipo.codigo,
                "categoria": self.categoria.pk,
                "marca": "",
                "modelo": "",
                "numero_serie": "",
                "fecha_compra": "",
                "costo_compra": "",
                "ambiente": self.ambiente.pk,
                "responsable": "",
                "estado": Equipo.Estado.DADO_DE_BAJA,
                "observaciones": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.estado, Equipo.Estado.OPERATIVO)
