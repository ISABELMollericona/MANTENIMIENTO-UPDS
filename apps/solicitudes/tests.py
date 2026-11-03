from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.cuentas.models import AuditoriaSeguridad, Rol, Usuario
from apps.equipos.models import CategoriaEquipo, Equipo
from apps.ubicaciones.models import Ambiente

from .models import Solicitud
from .services import asignar_tecnico, cambiar_estado


class SolicitudesTests(TestCase):
    def setUp(self):
        call_command("seed_roles", verbosity=0)
        self.rol_responsable = Rol.objects.get(nombre="Responsable de equipamiento")
        self.rol_tecnico = Rol.objects.get(nombre="Técnico")
        self.rol_solicitante = Rol.objects.get(nombre="Solicitante")
        permisos = Permission.objects.filter(content_type__app_label="cuentas", codename__in=["ver_solicitudes", "crear_solicitudes", "ver_todas_solicitudes", "asignar_tecnico", "cambiar_estado_solicitud", "reabrir_solicitud", "cancelar_solicitudes", "crear_intervenciones", "ver_equipos"])
        self.rol_responsable.grupo.permissions.add(*permisos)
        self.solicitante = Usuario.objects.create_user(username="docente", password="Clave-Segura-2026!")
        self.solicitante.groups.add(self.rol_solicitante.grupo)
        self.responsable = Usuario.objects.create_user(username="responsable", password="Clave-Segura-2026!")
        self.responsable.groups.add(self.rol_responsable.grupo)
        self.tecnico = Usuario.objects.create_user(username="tecnico", password="Clave-Segura-2026!")
        self.tecnico.groups.add(self.rol_tecnico.grupo)
        self.ambiente = Ambiente.objects.create(nombre="Laboratorio", tipo="laboratorio", bloque="A")
        categoria = CategoriaEquipo.objects.create(nombre="Computadora")
        self.equipo = Equipo.objects.create(codigo="EQ-001", categoria=categoria, ambiente=self.ambiente)
        self.solicitud = Solicitud.objects.create(equipo=self.equipo, descripcion="No enciende la computadora", solicitante=self.solicitante, creado_por=self.solicitante)

    def test_transiciones_validas_guardan_historial_y_cambian_estado_equipo(self):
        asignada = asignar_tecnico(self.solicitud, self.tecnico, self.responsable)
        self.assertEqual(asignada.estado, Solicitud.Estado.ASIGNADA)
        cambiar_estado(asignada, Solicitud.Estado.EN_REPARACION, self.tecnico, "Se inició el diagnóstico")
        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.estado, Equipo.Estado.EN_MANTENIMIENTO)
        cambiar_estado(asignada, Solicitud.Estado.RESUELTA, self.tecnico, "Equipo probado")
        self.equipo.refresh_from_db()
        asignada.refresh_from_db()
        self.assertEqual(self.equipo.estado, Equipo.Estado.OPERATIVO)
        self.assertEqual(asignada.historial.count(), 3)
        self.assertTrue(asignada.fecha_cierre)

    def test_transicion_invalida_no_modifica_historial_ni_equipo(self):
        with self.assertRaisesMessage(ValidationError, "No se puede cambiar de Registrada a Resuelta"):
            cambiar_estado(self.solicitud, Solicitud.Estado.RESUELTA, self.responsable)
        self.solicitud.refresh_from_db()
        self.equipo.refresh_from_db()
        self.assertEqual(self.solicitud.estado, Solicitud.Estado.REGISTRADA)
        self.assertEqual(self.equipo.estado, Equipo.Estado.OPERATIVO)
        self.assertEqual(self.solicitud.historial.count(), 0)

    def test_cancelacion_exige_motivo_y_reapertura_registra_nuevo_evento(self):
        asignar_tecnico(self.solicitud, self.tecnico, self.responsable)
        with self.assertRaisesMessage(ValidationError, "Indica el motivo de cancelación"):
            cambiar_estado(self.solicitud, Solicitud.Estado.CANCELADA, self.responsable)
        cambiar_estado(self.solicitud, Solicitud.Estado.CANCELADA, self.responsable, motivo_cancelacion="Duplicada")
        cambiar_estado(self.solicitud, Solicitud.Estado.REGISTRADA, self.responsable, comentario="Se requiere nueva revisión")
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, Solicitud.Estado.REGISTRADA)
        self.assertIsNone(self.solicitud.fecha_cierre)
        self.assertEqual(self.solicitud.historial.count(), 3)

    def test_resultado_no_reparable_deja_equipo_fuera_de_servicio(self):
        asignar_tecnico(self.solicitud, self.tecnico, self.responsable)
        cambiar_estado(self.solicitud, Solicitud.Estado.EN_REPARACION, self.tecnico)
        cambiar_estado(self.solicitud, Solicitud.Estado.RESUELTA, self.tecnico, no_reparable=True)
        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.estado, Equipo.Estado.FUERA_DE_SERVICIO)

    def test_solicitante_solo_ve_sus_solicitudes(self):
        otra = Usuario.objects.create_user(username="otra", password="Clave-Segura-2026!")
        otra_solicitud = Solicitud.objects.create(equipo=self.equipo, descripcion="Falla en otro usuario", solicitante=otra)
        self.client.force_login(self.solicitante)
        respuesta = self.client.get(reverse("solicitudes:lista"))
        self.assertContains(respuesta, f"#{self.solicitud.pk}")
        self.assertNotContains(respuesta, f"#{otra_solicitud.pk}")
        self.assertEqual(self.client.get(reverse("solicitudes:detalle", args=[otra_solicitud.pk])).status_code, 404)

    def test_asignar_tecnico_audita_y_sin_permiso_es_rechazado(self):
        asignar_tecnico(self.solicitud, self.tecnico, self.responsable)
        auditoria = AuditoriaSeguridad.objects.get(accion="tecnico_asignado")
        self.assertEqual(auditoria.usuario, self.responsable)
        with self.assertRaises(PermissionDenied):
            asignar_tecnico(self.solicitud, self.tecnico, self.solicitante)

    def test_solicitante_puede_cancelar_su_propia_solicitud_con_permiso_especial(self):
        self.rol_solicitante.grupo.permissions.add(Permission.objects.get(content_type__app_label="cuentas", codename="cancelar_solicitudes"))
        self.client.force_login(self.solicitante)
        respuesta = self.client.post(
            reverse("solicitudes:cambiar_estado", args=[self.solicitud.pk]),
            {"estado": Solicitud.Estado.CANCELADA, "motivo_cancelacion": "Ya no se requiere", "comentario": ""},
        )
        self.assertRedirects(respuesta, reverse("solicitudes:detalle", args=[self.solicitud.pk]))
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, Solicitud.Estado.CANCELADA)

    def test_filtros_de_solicitudes_y_creacion_desde_interfaz(self):
        self.client.force_login(self.responsable)
        respuesta = self.client.post(reverse("solicitudes:crear"), {"equipo": self.equipo.pk, "descripcion": "Proyector muestra pantalla negra", "prioridad": "alta"})
        self.assertEqual(respuesta.status_code, 302)
        nueva = Solicitud.objects.get(descripcion="Proyector muestra pantalla negra")
        self.assertEqual(nueva.solicitante, self.responsable)
        respuesta = self.client.get(reverse("solicitudes:lista"), {"estado": "registrada", "prioridad": "alta", "ambiente": self.ambiente.pk})
        self.assertContains(respuesta, f"#{nueva.pk}")