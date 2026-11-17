from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import Rol, Usuario
from apps.equipos.models import CategoriaEquipo, Equipo
from apps.preventivo.models import MantenimientoPreventivo
from apps.solicitudes.models import Solicitud
from apps.solicitudes.services import asignar_tecnico
from apps.ubicaciones.models import Ambiente

from .models import Intervencion


class ReparacionesTests(TestCase):
    def setUp(self):
        call_command("seed_roles", verbosity=0)
        self.responsable = Usuario.objects.create_user(username="responsable", password="Clave-Segura-2026!")
        self.responsable.groups.add(Rol.objects.get(nombre="Responsable de mantenimiento").grupo)
        self.tecnico = Usuario.objects.create_user(username="tecnico", password="Clave-Segura-2026!")
        self.tecnico.groups.add(Rol.objects.get(nombre="Técnico").grupo)
        self.otro_tecnico = Usuario.objects.create_user(username="tecnico2", password="Clave-Segura-2026!")
        self.otro_tecnico.groups.add(Rol.objects.get(nombre="Técnico").grupo)
        self.jefe = Usuario.objects.create_user(username="jefe", password="Clave-Segura-2026!")
        self.jefe.groups.add(Rol.objects.get(nombre="Jefe de carrera").grupo)
        self.ambiente = Ambiente.objects.create(nombre="Laboratorio 1", tipo="laboratorio", bloque="A")
        categoria = CategoriaEquipo.objects.create(nombre="Computadora")
        self.equipo = Equipo.objects.create(codigo="EQ-001", categoria=categoria, ambiente=self.ambiente)
        self.solicitud = Solicitud.objects.create(equipo=self.equipo, docente_solicitante="Lic. Rojas", descripcion="No enciende la computadora", solicitante=self.jefe, fecha_reporte=timezone.now() - timedelta(days=20))
        asignar_tecnico(self.solicitud, self.tecnico, self.responsable)
        self.hoy = timezone.localdate()

    def _salida(self, **extra):
        datos = {"fecha_salida": (self.hoy - timedelta(days=5)).isoformat(), "diagnostico": "Fuente de poder dañada", "trabajo_realizado": "", "repuestos_usados": "", "fecha_devolucion": "", "resultado": "", "observaciones": ""}
        datos.update(extra)
        return self.client.post(reverse("intervenciones:crear", args=[self.solicitud.pk]), datos)

    def test_salida_y_devolucion_completan_la_reparacion(self):
        self.client.force_login(self.tecnico)
        self.assertRedirects(self._salida(), reverse("solicitudes:detalle", args=[self.solicitud.pk]))
        reparacion = Intervencion.objects.get()
        self.solicitud.refresh_from_db()
        self.equipo.refresh_from_db()
        self.assertEqual(self.solicitud.estado, Solicitud.Estado.EN_REPARACION)
        self.assertTrue(self.equipo.esta_en_reparacion)
        self.assertEqual(reparacion.laboratorio_origen, self.ambiente)
        self.assertEqual(reparacion.dias_fuera, 5)

        respuesta = self.client.post(reverse("intervenciones:editar", args=[reparacion.pk]), {
            "fecha_salida": reparacion.fecha_salida.isoformat(), "diagnostico": "Fuente de poder dañada",
            "trabajo_realizado": "Se cambió la fuente", "repuestos_usados": "Fuente 500 W",
            "fecha_devolucion": (self.hoy - timedelta(days=1)).isoformat(), "resultado": "reparado", "observaciones": "",
        })
        self.assertRedirects(respuesta, reverse("solicitudes:detalle", args=[self.solicitud.pk]))
        reparacion.refresh_from_db()
        self.solicitud.refresh_from_db()
        self.equipo.refresh_from_db()
        self.assertEqual((reparacion.dias_fuera, reparacion.repuestos_usados), (4, "Fuente 500 W"))
        self.assertEqual(self.solicitud.estado, Solicitud.Estado.RESUELTA)
        self.assertTrue(self.equipo.esta_operativo)

    def test_devolucion_no_puede_ser_anterior_a_la_salida(self):
        self.client.force_login(self.tecnico)
        respuesta = self._salida(fecha_devolucion=(self.hoy - timedelta(days=7)).isoformat(), resultado="reparado", trabajo_realizado="x")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("fecha_devolucion", respuesta.context["form"].errors)
        self.assertFalse(Intervencion.objects.exists())

    def test_salida_no_puede_ser_anterior_al_reporte(self):
        self.client.force_login(self.tecnico)
        respuesta = self._salida(fecha_salida=(self.hoy - timedelta(days=30)).isoformat())
        self.assertIn("fecha_salida", respuesta.context["form"].errors)

    def test_campos_obligatorios_de_la_reparacion(self):
        self.client.force_login(self.tecnico)
        respuesta = self._salida(fecha_salida="", diagnostico="", fecha_devolucion=self.hoy.isoformat())
        errores = respuesta.context["form"].errors
        for campo in ("fecha_salida", "diagnostico", "resultado", "trabajo_realizado"):
            self.assertIn(campo, errores)

    def test_no_reparable_deja_el_equipo_en_reparacion_para_la_baja(self):
        self.client.force_login(self.tecnico)
        self._salida(trabajo_realizado="Placa madre quemada", fecha_devolucion=self.hoy.isoformat(), resultado="no_reparable")
        self.equipo.refresh_from_db()
        self.assertTrue(self.equipo.esta_en_reparacion)

    def test_solo_el_tecnico_asignado_registra_y_edita(self):
        self.client.force_login(self.otro_tecnico)
        self.assertEqual(self._salida().status_code, 403)
        self.client.force_login(self.tecnico)
        self._salida()
        reparacion = Intervencion.objects.get()
        self.client.force_login(self.otro_tecnico)
        self.assertEqual(self.client.get(reverse("intervenciones:editar", args=[reparacion.pk])).status_code, 403)
        self.client.force_login(self.jefe)
        self.assertEqual(self.client.get(reverse("intervenciones:editar", args=[reparacion.pk])).status_code, 403)

    def test_tecnico_solo_ve_sus_reparaciones_y_preventivos(self):
        otra = Solicitud.objects.create(equipo=self.equipo, docente_solicitante="Ing. Pérez", descripcion="Otra falla ajena", solicitante=self.jefe)
        asignar_tecnico(otra, self.otro_tecnico, self.responsable)
        propio = MantenimientoPreventivo.objects.create(laboratorio=self.ambiente, anio=self.hoy.year, numero=1, fecha_programada=self.hoy.replace(month=12, day=1), tecnico=self.tecnico)
        Ambiente.objects.create(nombre="Laboratorio 2", tipo="laboratorio", bloque="B")
        self.client.force_login(self.tecnico)
        respuesta = self.client.get(reverse("intervenciones:mis_tareas"))
        self.assertContains(respuesta, f"#{self.solicitud.pk}")
        self.assertNotContains(respuesta, f"#{otra.pk}")
        self.assertEqual(list(respuesta.context["preventivos"]), [propio])
        self.assertEqual(self.client.get(reverse("solicitudes:detalle", args=[otra.pk])).status_code, 404)

    def test_reparacion_no_tiene_campos_de_costo(self):
        campos = {campo.name for campo in Intervencion._meta.get_fields()}
        self.assertFalse({c for c in campos if "costo" in c})
        self.assertIn("repuestos_usados", campos)


    def test_no_se_resuelve_sin_registrar_la_devolucion(self):
        from django.core.exceptions import ValidationError

        from apps.solicitudes.services import cambiar_estado

        self.client.force_login(self.tecnico)
        self._salida()
        self.solicitud.refresh_from_db()
        opciones = [v for v, _ in self.client.get(reverse("solicitudes:detalle", args=[self.solicitud.pk])).context["estado_form"].fields["estado"].choices]
        self.assertNotIn(Solicitud.Estado.RESUELTA, opciones)
        with self.assertRaises(ValidationError):
            cambiar_estado(self.solicitud, Solicitud.Estado.RESUELTA, self.tecnico)


class MensajeDevolucionTests(TestCase):
    def test_devolucion_anterior_muestra_un_solo_error(self):
        from datetime import date

        from .forms import IntervencionForm

        form = IntervencionForm(data={"fecha_salida": "2026-11-10", "diagnostico": "Fuente dañada", "trabajo_realizado": "Cambio", "repuestos_usados": "", "fecha_devolucion": "2026-11-05", "resultado": "reparado", "observaciones": ""})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["fecha_devolucion"], ["La fecha de devolución debe ser igual o posterior a la fecha de salida."])
