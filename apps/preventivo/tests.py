from datetime import date

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import Rol, Usuario
from apps.ubicaciones.models import Ambiente

from .models import MantenimientoPreventivo


class CronogramaPreventivoTests(TestCase):
    def setUp(self):
        call_command("seed_roles", verbosity=0)
        self.responsable = Usuario.objects.create_user(username="responsable", password="Clave-Segura-2026!")
        self.responsable.groups.add(Rol.objects.get(nombre="Responsable de mantenimiento").grupo)
        self.tecnico = Usuario.objects.create_user(username="tecnico", password="Clave-Segura-2026!")
        self.tecnico.groups.add(Rol.objects.get(nombre="Técnico").grupo)
        self.otro_tecnico = Usuario.objects.create_user(username="tecnico2", password="Clave-Segura-2026!")
        self.otro_tecnico.groups.add(Rol.objects.get(nombre="Técnico").grupo)
        self.lab = Ambiente.objects.create(nombre="Laboratorio 1", tipo="laboratorio", bloque="A")
        self.anio = timezone.localdate().year

    def _cargar(self, **extra):
        datos = {"laboratorio": self.lab.pk, "anio": self.anio, "fecha_1": f"{self.anio}-02-10", "fecha_2": f"{self.anio}-07-10", "fecha_3": "", "tecnico": self.tecnico.pk}
        datos.update(extra)
        return self.client.post(reverse("preventivo:cargar"), datos)

    def test_responsable_carga_cronograma_anual_con_2_o_3_mantenimientos(self):
        self.client.force_login(self.responsable)
        self.assertEqual(self._cargar().status_code, 302)
        self.assertEqual(MantenimientoPreventivo.objects.filter(laboratorio=self.lab, anio=self.anio).count(), 2)
        self._cargar(fecha_3=f"{self.anio}-11-10")
        self.assertEqual(list(MantenimientoPreventivo.objects.filter(laboratorio=self.lab, anio=self.anio).values_list("numero", flat=True)), [1, 2, 3])

    def test_fechas_deben_ser_del_anio_y_en_orden(self):
        self.client.force_login(self.responsable)
        respuesta = self._cargar(fecha_1=f"{self.anio + 1}-01-10", fecha_2=f"{self.anio}-01-01")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("fecha_1", respuesta.context["form"].errors)
        respuesta = self._cargar(fecha_1=f"{self.anio}-08-10", fecha_2=f"{self.anio}-03-10")
        self.assertIn("fecha_2", respuesta.context["form"].errors)
        respuesta = self._cargar(fecha_2="")
        self.assertIn("fecha_2", respuesta.context["form"].errors)
        self.assertFalse(MantenimientoPreventivo.objects.exists())

    def test_marcar_realizado_y_volver_a_pendiente(self):
        mantenimiento = MantenimientoPreventivo.objects.create(laboratorio=self.lab, anio=self.anio, numero=1, fecha_programada=date(self.anio, 1, 15), tecnico=self.tecnico)
        self.client.force_login(self.tecnico)
        respuesta = self.client.post(reverse("preventivo:marcar", args=[mantenimiento.pk]), {"fecha_realizada": timezone.localdate().isoformat(), "observaciones": "Limpieza"})
        self.assertEqual(respuesta.status_code, 302)
        mantenimiento.refresh_from_db()
        self.assertEqual(mantenimiento.estado, MantenimientoPreventivo.Estado.REALIZADO)
        self.client.post(reverse("preventivo:pendiente", args=[mantenimiento.pk]))
        mantenimiento.refresh_from_db()
        self.assertEqual((mantenimiento.estado, mantenimiento.fecha_realizada), (MantenimientoPreventivo.Estado.PENDIENTE, None))

    def test_tecnico_solo_ve_y_marca_sus_mantenimientos(self):
        propio = MantenimientoPreventivo.objects.create(laboratorio=self.lab, anio=self.anio, numero=1, fecha_programada=date(self.anio, 3, 1), tecnico=self.tecnico)
        ajeno = MantenimientoPreventivo.objects.create(laboratorio=self.lab, anio=self.anio, numero=2, fecha_programada=date(self.anio, 9, 1), tecnico=self.otro_tecnico)
        self.client.force_login(self.tecnico)
        respuesta = self.client.get(reverse("preventivo:cronograma"))
        celdas = [m for fila in respuesta.context["filas"] for m in fila["celdas"] if m]
        self.assertEqual(celdas, [propio])
        self.assertEqual(self.client.post(reverse("preventivo:marcar", args=[ajeno.pk]), {"fecha_realizada": timezone.localdate().isoformat()}).status_code, 403)
        self.assertEqual(self.client.get(reverse("preventivo:cargar")).status_code, 403)

    def test_no_se_puede_marcar_realizado_en_fecha_futura(self):
        mantenimiento = MantenimientoPreventivo.objects.create(laboratorio=self.lab, anio=self.anio, numero=1, fecha_programada=date(self.anio, 1, 15))
        self.client.force_login(self.responsable)
        manana = timezone.localdate().replace(year=self.anio + 1).isoformat()
        respuesta = self.client.post(reverse("preventivo:marcar", args=[mantenimiento.pk]), {"fecha_realizada": manana})
        self.assertEqual(respuesta.status_code, 200)
        mantenimiento.refresh_from_db()
        self.assertEqual(mantenimiento.estado, MantenimientoPreventivo.Estado.PENDIENTE)
