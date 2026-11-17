"""Matriz de acceso por rol: se prueban las URLs directamente, no solo los botones."""

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import Rol, Usuario
from apps.equipos.models import CategoriaEquipo, Equipo
from apps.preventivo.models import MantenimientoPreventivo
from apps.solicitudes.models import Solicitud
from apps.ubicaciones.models import Ambiente


class AccesoPorRolTests(TestCase):
    def setUp(self):
        call_command("seed_roles", verbosity=0)
        self.usuarios = {}
        for nombre in ("Administrador", "Responsable de mantenimiento", "Técnico", "Jefe de carrera", "Estudiante"):
            usuario = Usuario.objects.create_user(username=nombre.split()[0].lower(), password="Clave-Segura-2026!")
            usuario.groups.add(Rol.objects.get(nombre=nombre).grupo)
            self.usuarios[nombre] = usuario
        lab = Ambiente.objects.create(nombre="Laboratorio 1", tipo="laboratorio", bloque="A")
        self.equipo = Equipo.objects.create(codigo="PC-01", categoria=CategoriaEquipo.objects.create(nombre="Computadora"), ambiente=lab)
        self.reporte = Solicitud.objects.create(equipo=self.equipo, docente_solicitante="Lic. Rojas", descripcion="No enciende", solicitante=self.usuarios["Jefe de carrera"])
        self.preventivo = MantenimientoPreventivo.objects.create(laboratorio=lab, anio=timezone.localdate().year, numero=1, fecha_programada=timezone.localdate().replace(month=1, day=10))

    def _verificar(self, rol, permitidas, prohibidas):
        self.client.force_login(self.usuarios[rol])
        for url in permitidas:
            with self.subTest(rol=rol, url=url, esperado=200):
                self.assertEqual(self.client.get(url).status_code, 200)
        for url in prohibidas:
            with self.subTest(rol=rol, url=url, esperado=403):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_administrador_crea_usuarios_y_asigna_roles(self):
        self._verificar("Administrador", [reverse("cuentas:usuarios"), reverse("cuentas:usuario_crear"), reverse("cuentas:roles")], [])

    def test_responsable_de_mantenimiento(self):
        self._verificar(
            "Responsable de mantenimiento",
            [reverse("equipos:crear"), reverse("equipos:bajas"), reverse("equipos:estados"), reverse("solicitudes:lista"),
             reverse("solicitudes:detalle", args=[self.reporte.pk]), reverse("preventivo:cargar"), reverse("reportes:lista"), reverse("equipos:baja", args=[self.equipo.pk])],
            [reverse("cuentas:usuarios"), reverse("cuentas:usuario_crear"), reverse("cuentas:roles"), reverse("solicitudes:crear")],
        )

    def test_tecnico_solo_lo_asignado(self):
        self._verificar(
            "Técnico",
            [reverse("intervenciones:mis_tareas"), reverse("solicitudes:lista"), reverse("preventivo:cronograma")],
            [reverse("equipos:lista"), reverse("equipos:crear"), reverse("equipos:bajas"), reverse("solicitudes:crear"), reverse("reportes:lista"),
             reverse("preventivo:cargar"), reverse("preventivo:marcar", args=[self.preventivo.pk]), reverse("cuentas:usuarios"), reverse("ubicaciones:lista")],
        )
        # Un reporte que no tiene asignado no existe para él.
        self.assertEqual(self.client.get(reverse("solicitudes:detalle", args=[self.reporte.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("solicitudes:asignar_tecnico", args=[self.reporte.pk]), {"tecnico": self.usuarios["Técnico"].pk}).status_code, 403)

    def test_jefe_de_carrera_solo_registra_reportes(self):
        self._verificar(
            "Jefe de carrera",
            [reverse("solicitudes:crear"), reverse("solicitudes:lista"), reverse("solicitudes:detalle", args=[self.reporte.pk])],
            [reverse("equipos:lista"), reverse("equipos:crear"), reverse("reportes:lista"), reverse("preventivo:cronograma"),
             reverse("intervenciones:mis_tareas"), reverse("cuentas:usuarios"), reverse("ubicaciones:lista")],
        )
        self.assertEqual(self.client.post(reverse("solicitudes:cambiar_estado", args=[self.reporte.pk]), {"estado": "asignada"}).status_code, 403)

    def test_estudiante_solo_consulta_el_estado_de_los_equipos(self):
        self._verificar(
            "Estudiante",
            [reverse("equipos:lista"), reverse("equipos:ficha", args=[self.equipo.pk])],
            [reverse("equipos:crear"), reverse("equipos:editar", args=[self.equipo.pk]), reverse("equipos:bajas"), reverse("equipos:estados"),
             reverse("solicitudes:lista"), reverse("solicitudes:crear"), reverse("reportes:lista"), reverse("preventivo:cronograma"),
             reverse("intervenciones:mis_tareas"), reverse("cuentas:usuarios"), reverse("ubicaciones:lista")],
        )
        # Tampoco puede modificar enviando formularios directamente.
        self.assertEqual(self.client.post(reverse("equipos:editar", args=[self.equipo.pk]), {"codigo": "X"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("solicitudes:crear"), {"docente_solicitante": "X", "equipo": self.equipo.pk, "descripcion": "Prueba de acceso"}).status_code, 403)
        ficha = self.client.get(reverse("equipos:ficha", args=[self.equipo.pk]))
        self.assertNotContains(ficha, "Editar")
        self.assertNotContains(ficha, "Registrar baja")
