from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import Rol, Usuario
from apps.equipos.models import CategoriaEquipo, Equipo
from apps.solicitudes.models import Solicitud
from apps.solicitudes.services import asignar_tecnico
from apps.ubicaciones.models import Ambiente

from .models import Intervencion, RepuestoUsado


class IntervencionesTests(TestCase):
    def setUp(self):
        call_command("seed_roles", verbosity=0)
        self.rol_responsable = Rol.objects.get(nombre="Responsable de equipamiento")
        self.rol_tecnico = Rol.objects.get(nombre="Técnico")
        self.rol_solicitante = Rol.objects.get(nombre="Solicitante")
        self.responsable = Usuario.objects.create_user(username="responsable", password="Clave-Segura-2026!")
        self.responsable.groups.add(self.rol_responsable.grupo)
        self.tecnico = Usuario.objects.create_user(username="tecnico", password="Clave-Segura-2026!")
        self.tecnico.groups.add(self.rol_tecnico.grupo)
        self.otro_tecnico = Usuario.objects.create_user(username="tecnico2", password="Clave-Segura-2026!")
        self.otro_tecnico.groups.add(self.rol_tecnico.grupo)
        self.solicitante = Usuario.objects.create_user(username="docente", password="Clave-Segura-2026!")
        self.solicitante.groups.add(self.rol_solicitante.grupo)
        self.ambiente = Ambiente.objects.create(nombre="Laboratorio", tipo="laboratorio", bloque="A")
        categoria = CategoriaEquipo.objects.create(nombre="Computadora")
        self.equipo = Equipo.objects.create(codigo="EQ-001", categoria=categoria, ambiente=self.ambiente)
        self.solicitud = Solicitud.objects.create(equipo=self.equipo, descripcion="No enciende la computadora", solicitante=self.solicitante)
        asignar_tecnico(self.solicitud, self.tecnico, self.responsable)

    def post_intervencion(self, fin=None, resultado="", costo="80.00", cantidad="2", precio="15.50"):
        ahora = timezone.localtime()
        inicio = ahora - timedelta(minutes=10) if fin else ahora
        data = {
            "diagnostico": "Falla en la fuente de alimentación",
            "trabajo_realizado": "Se revisó el cableado",
            "fecha_inicio": inicio.strftime("%Y-%m-%dT%H:%M"),
            "fecha_fin": fin.strftime("%Y-%m-%dT%H:%M") if fin else "",
            "costo_mano_obra": costo,
            "resultado": resultado,
            "observaciones": "Prueba controlada",
            "repuestos-TOTAL_FORMS": "1",
            "repuestos-INITIAL_FORMS": "0",
            "repuestos-MIN_NUM_FORMS": "0",
            "repuestos-MAX_NUM_FORMS": "15",
            "repuestos-0-descripcion": "Cable de poder",
            "repuestos-0-cantidad": cantidad,
            "repuestos-0-costo_unitario": precio,
        }
        return self.client.post(reverse("intervenciones:crear", args=[self.solicitud.pk]), data)

    def test_intervencion_con_repuestos_calcula_total_y_cierra_solicitud(self):
        self.client.force_login(self.tecnico)
        respuesta = self.post_intervencion(fin=timezone.localtime(), resultado=Intervencion.Resultado.REPARADO)
        self.assertRedirects(respuesta, reverse("solicitudes:detalle", args=[self.solicitud.pk]))
        intervencion = Intervencion.objects.get(solicitud=self.solicitud)
        self.assertEqual(intervencion.costo_total, Decimal("111.00"))
        self.assertEqual(intervencion.repuestos.count(), 1)
        self.solicitud.refresh_from_db()
        self.equipo.refresh_from_db()
        self.assertEqual(self.solicitud.estado, Solicitud.Estado.RESUELTA)
        self.assertEqual(self.equipo.estado, Equipo.Estado.OPERATIVO)

    def test_resultado_no_reparable_deja_equipo_fuera_de_servicio(self):
        self.client.force_login(self.tecnico)
        self.post_intervencion(fin=timezone.localtime(), resultado=Intervencion.Resultado.NO_REPARABLE)
        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.estado, Equipo.Estado.FUERA_DE_SERVICIO)

    def test_solicitud_admite_varias_intervenciones(self):
        self.client.force_login(self.tecnico)
        self.post_intervencion()
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, Solicitud.Estado.EN_REPARACION)
        self.post_intervencion(fin=timezone.localtime(), resultado=Intervencion.Resultado.PARCIAL)
        self.assertEqual(Intervencion.objects.filter(solicitud=self.solicitud).count(), 2)

    def test_tecnico_solo_puede_atender_solicitud_asignada_a_el(self):
        self.solicitud.tecnico_asignado = self.otro_tecnico
        self.solicitud.save(update_fields=["tecnico_asignado", "actualizado_en"])
        self.client.force_login(self.tecnico)
        respuesta = self.client.get(reverse("intervenciones:crear", args=[self.solicitud.pk]))
        self.assertEqual(respuesta.status_code, 403)

    def test_solicitud_resuelta_no_acepta_nuevas_intervenciones(self):
        self.solicitud.estado = Solicitud.Estado.RESUELTA
        self.solicitud.save(update_fields=["estado", "actualizado_en"])
        self.client.force_login(self.tecnico)
        respuesta = self.client.get(reverse("intervenciones:crear", args=[self.solicitud.pk]))
        self.assertEqual(respuesta.status_code, 404)

    def test_mis_tareas_ordena_prioridad_y_antiguedad(self):
        alta_antigua = Solicitud.objects.create(equipo=self.equipo, descripcion="Falla urgente del equipo", solicitante=self.solicitante, tecnico_asignado=self.tecnico, estado=Solicitud.Estado.ASIGNADA, prioridad=Solicitud.Prioridad.ALTA, fecha_reporte=timezone.now() - timedelta(days=3))
        alta_nueva = Solicitud.objects.create(equipo=self.equipo, descripcion="Falla prioritaria reciente", solicitante=self.solicitante, tecnico_asignado=self.tecnico, estado=Solicitud.Estado.ASIGNADA, prioridad=Solicitud.Prioridad.ALTA, fecha_reporte=timezone.now() - timedelta(days=1))
        media = Solicitud.objects.create(equipo=self.equipo, descripcion="Falla de prioridad media", solicitante=self.solicitante, tecnico_asignado=self.tecnico, estado=Solicitud.Estado.ASIGNADA, prioridad=Solicitud.Prioridad.MEDIA)
        self.client.force_login(self.tecnico)
        respuesta = self.client.get(reverse("intervenciones:mis_tareas"))
        ids = [solicitud.pk for solicitud in respuesta.context["solicitudes"]]
        self.assertLess(ids.index(alta_antigua.pk), ids.index(alta_nueva.pk))
        self.assertLess(ids.index(alta_nueva.pk), ids.index(media.pk))

    def test_ficha_de_equipo_muestra_costos_y_fallas_acumuladas(self):
        inicio = timezone.now()
        intervencion = Intervencion.objects.create(solicitud=self.solicitud, tecnico=self.tecnico, diagnostico="Prueba", fecha_inicio=inicio, costo_mano_obra=Decimal("35.00"))
        RepuestoUsado.objects.create(intervencion=intervencion, descripcion="Adaptador", cantidad=Decimal("2"), costo_unitario=Decimal("7.50"))
        self.client.force_login(self.tecnico)
        self.tecnico.groups.add(self.rol_responsable.grupo)
        response = self.client.get(reverse("equipos:ficha", args=[self.equipo.pk]))
        self.assertEqual(response.context["costo_acumulado"], Decimal("50.00"))
        self.assertEqual(response.context["cantidad_fallas"], 1)