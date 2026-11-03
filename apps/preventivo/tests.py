from datetime import date, timedelta

from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import Rol, Usuario
from apps.equipos.models import CategoriaEquipo, Equipo
from apps.ubicaciones.models import Ambiente

from .forms import MantenimientoProgramadoForm
from .models import MantenimientoProgramado, PlanPreventivo
from .services import agregar_meses, completar_mantenimiento


class PreventivoTests(TestCase):
    def setUp(self):
        call_command("seed_roles", verbosity=0)
        self.rol = Rol.objects.get(nombre="Responsable de equipamiento")
        self.rol.grupo.permissions.add(*Permission.objects.filter(content_type__app_label="cuentas", codename__in=["ver_preventivos", "crear_preventivos", "editar_preventivos"]))
        self.usuario = Usuario.objects.create_user(username="responsable", password="Clave-Segura-2026!")
        self.usuario.groups.add(self.rol.grupo)
        ambiente = Ambiente.objects.create(nombre="Laboratorio", tipo="laboratorio", bloque="A")
        self.categoria = CategoriaEquipo.objects.create(nombre="Proyector")
        self.equipo = Equipo.objects.create(codigo="EQ-001", categoria=self.categoria, ambiente=ambiente)
        self.plan = PlanPreventivo.objects.create(categoria=self.categoria, nombre="Limpieza semestral", periodicidad_meses=6, actividades="Limpiar filtros y verificar lámpara.", creado_por=self.usuario)
        self.programado = MantenimientoProgramado.objects.create(equipo=self.equipo, plan=self.plan, fecha_programada=timezone.localdate() - timedelta(days=1), creado_por=self.usuario)
        self.client.force_login(self.usuario)

    def test_agregar_meses_ajusta_fin_de_mes_y_anio_bisiesto(self):
        self.assertEqual(agregar_meses(date(2024, 1, 31), 1), date(2024, 2, 29))
        self.assertEqual(agregar_meses(date(2025, 1, 31), 1), date(2025, 2, 28))
        self.assertEqual(agregar_meses(date(2026, 11, 30), 4), date(2027, 3, 30))

    def test_vencido_se_calcula_solo_para_pendientes_con_fecha_pasada(self):
        self.assertTrue(self.programado.vencido)
        futuro = MantenimientoProgramado.objects.create(equipo=self.equipo, plan=self.plan, fecha_programada=timezone.localdate() + timedelta(days=1))
        self.assertFalse(futuro.vencido)
        self.programado.estado = MantenimientoProgramado.Estado.REALIZADO
        self.assertFalse(self.programado.vencido)

    def test_completar_programacion_crea_siguiente_segun_periodicidad(self):
        realizado, siguiente = completar_mantenimiento(self.programado, self.usuario)
        self.assertEqual(realizado.estado, MantenimientoProgramado.Estado.REALIZADO)
        self.assertEqual(realizado.fecha_realizada, timezone.localdate())
        self.assertEqual(siguiente.fecha_programada, agregar_meses(realizado.fecha_realizada, 6))
        self.assertEqual(MantenimientoProgramado.objects.filter(equipo=self.equipo, plan=self.plan).count(), 2)

    def test_completar_dos_veces_no_duplica_el_siguiente(self):
        completar_mantenimiento(self.programado, self.usuario)
        _, siguiente = completar_mantenimiento(self.programado, self.usuario)
        self.assertIsNone(siguiente)
        self.assertEqual(MantenimientoProgramado.objects.filter(equipo=self.equipo, plan=self.plan).count(), 2)

    def test_lista_muestra_vencidos_y_permite_confirmar_realizacion(self):
        respuesta = self.client.get(reverse("preventivo:programaciones"))
        self.assertContains(respuesta, "Vencido")
        self.assertContains(respuesta, "EQ-001")
        respuesta = self.client.post(reverse("preventivo:completar", args=[self.programado.pk]))
        self.assertRedirects(respuesta, reverse("preventivo:programaciones"))
        self.assertEqual(MantenimientoProgramado.objects.filter(equipo=self.equipo, plan=self.plan).count(), 2)

    def test_plan_no_se_puede_asignar_a_otra_categoria(self):
        otra_categoria = CategoriaEquipo.objects.create(nombre="Impresora")
        otro_equipo = Equipo.objects.create(codigo="EQ-002", categoria=otra_categoria)
        formulario = MantenimientoProgramadoForm(data={
            "equipo": otro_equipo.pk,
            "plan": self.plan.pk,
            "fecha_programada": timezone.localdate().isoformat(),
            "tecnico": "",
            "observaciones": "",
        })
        self.assertFalse(formulario.is_valid())
        self.assertIn("El plan debe corresponder a la categoría del equipo.", str(formulario.errors))

    def test_plan_se_crea_edita_y_desactiva_sin_borrarlo(self):
        respuesta = self.client.post(reverse("preventivo:plan_crear"), {
            "categoria": self.categoria.pk,
            "nombre": "Revisión eléctrica",
            "periodicidad_meses": 12,
            "actividades": "Revisar conectores y cableado.",
            "activo": "on",
        })
        self.assertRedirects(respuesta, reverse("preventivo:planes"))
        plan = PlanPreventivo.objects.get(nombre="Revisión eléctrica")
        respuesta = self.client.post(reverse("preventivo:plan_editar", args=[plan.pk]), {
            "categoria": self.categoria.pk,
            "nombre": plan.nombre,
            "periodicidad_meses": 12,
            "actividades": "Revisar conectores y cableado.",
        })
        self.assertRedirects(respuesta, reverse("preventivo:planes"))
        plan.refresh_from_db()
        self.assertFalse(plan.activo)
        self.assertTrue(PlanPreventivo.objects.filter(pk=plan.pk).exists())