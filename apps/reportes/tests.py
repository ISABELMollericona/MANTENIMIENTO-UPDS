from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.cuentas.models import Rol, Usuario
from apps.equipos.models import CategoriaEquipo, Equipo
from apps.intervenciones.models import Intervencion, RepuestoUsado
from apps.solicitudes.models import Solicitud
from apps.ubicaciones.models import Ambiente

from .services import DEFINICIONES_REPORTES, generar_reporte


class ReportesYPanelTests(TestCase):
    def setUp(self):
        call_command("seed_roles", verbosity=0)
        self.rol_autoridad = Rol.objects.get(nombre="Autoridad")
        self.rol_solicitante = Rol.objects.get(nombre="Solicitante")
        self.rol_autoridad.grupo.permissions.add(*Permission.objects.filter(
            content_type__app_label="cuentas",
            codename__in=["ver_dashboard", "ver_reportes", "exportar_reportes"],
        ))
        self.autoridad = Usuario.objects.create_user(username="autoridad", password="Clave-Segura-2026!")
        self.autoridad.groups.add(self.rol_autoridad.grupo)
        self.solicitante = Usuario.objects.create_user(username="docente", password="Clave-Segura-2026!")
        self.solicitante.groups.add(self.rol_solicitante.grupo)
        self.ambiente = Ambiente.objects.create(nombre="Laboratorio", tipo="laboratorio", bloque="A")
        self.categoria = CategoriaEquipo.objects.create(nombre="Proyector")
        self.equipo = Equipo.objects.create(
            codigo="EQ-001",
            categoria=self.categoria,
            marca="Epson",
            modelo="X1",
            fecha_compra=date(2022, 1, 1),
            costo_compra=Decimal("1000.00"),
            ambiente=self.ambiente,
            estado=Equipo.Estado.FUERA_DE_SERVICIO,
        )
        self.solicitud = Solicitud.objects.create(
            equipo=self.equipo,
            descripcion="La imagen del proyector parpadea",
            solicitante=self.solicitante,
            prioridad=Solicitud.Prioridad.ALTA,
        )
        self.client.force_login(self.autoridad)

    def test_los_siete_reportes_se_renderizan(self):
        for clave, _ in DEFINICIONES_REPORTES:
            with self.subTest(reporte=clave):
                respuesta = self.client.get(reverse("reportes:lista"), {"reporte": clave})
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, dict(DEFINICIONES_REPORTES)[clave])

    def test_filtros_de_fecha_ambiente_y_categoria(self):
        datos = generar_reporte("equipos_fuera_servicio", self.autoridad, {
            "desde": "2020-01-01",
            "hasta": "2030-01-01",
            "ambiente": str(self.ambiente.pk),
            "categoria": str(self.categoria.pk),
        })
        self.assertEqual(len(datos["filas"]), 1)
        sin_coincidencias = generar_reporte("equipos_fuera_servicio", self.autoridad, {"categoria": "99999"})
        self.assertEqual(sin_coincidencias["filas"], [])

    def test_exportaciones_excel_y_pdf_responden_con_formato_correcto(self):
        url = reverse("reportes:lista")
        excel = self.client.get(url, {"reporte": "equipos_fuera_servicio", "formato": "excel"})
        self.assertEqual(excel.status_code, 200)
        self.assertEqual(excel["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertTrue(excel.content.startswith(b"PK"))

        pdf = self.client.get(url, {"reporte": "equipos_fuera_servicio", "formato": "pdf"})
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_usuario_sin_permiso_no_accede_a_reportes(self):
        sin_permiso = Usuario.objects.create_user(username="sin_reportes", password="Clave-Segura-2026!")
        self.client.force_login(sin_permiso)
        self.assertEqual(self.client.get(reverse("reportes:lista")).status_code, 403)

    def test_sugerencia_compara_costos_sin_presentarse_como_decision(self):
        self.client.force_login(self.autoridad)
        respuesta = self.client.get(reverse("reportes:lista"), {"reporte": "reparar_reemplazar"})
        self.assertContains(respuesta, "sugerencia")
        self.assertContains(respuesta, "No reemplaza una decisión técnica")

    def test_dashboard_sin_permiso_de_solicitudes_no_expone_sus_detalles(self):
        self.client.force_login(self.autoridad)
        respuesta = self.client.get(reverse("panel"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, self.solicitud.descripcion)

    def test_solicitante_sin_permiso_de_dashboard_no_ve_indicadores(self):
        permiso_dashboard = Permission.objects.get(content_type__app_label="cuentas", codename="ver_dashboard")
        self.rol_solicitante.grupo.permissions.remove(permiso_dashboard)
        self.client.force_login(self.solicitante)
        respuesta = self.client.get(reverse("panel"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "no tiene permiso para ver los indicadores")
        self.assertNotContains(respuesta, "EQ-001")

    def test_reporte_de_historial_y_costo_incluye_repuestos(self):
        intervencion = Intervencion.objects.create(
            solicitud=self.solicitud,
            tecnico=self.autoridad,
            diagnostico="Lámpara agotada",
            trabajo_realizado="Cambio de lámpara",
            costo_mano_obra=Decimal("50.00"),
        )
        RepuestoUsado.objects.create(intervencion=intervencion, descripcion="Lámpara", cantidad=Decimal("1"), costo_unitario=Decimal("250.00"))
        self.rol_autoridad.grupo.permissions.add(Permission.objects.get(content_type__app_label="cuentas", codename="ver_todas_solicitudes"))
        historial = generar_reporte("historial_equipo", self.autoridad, {})
        costos = generar_reporte("costos_periodo", self.autoridad, {})
        self.assertEqual(historial["filas"][0]["Costo (Bs.)"], Decimal("300.00"))
        self.assertEqual(costos["filas"][-1]["Total intervención (Bs.)"], Decimal("300.00"))

    def test_indicador_no_suma_costos_de_solicitudes_fuera_del_alcance(self):
        otro_solicitante = Usuario.objects.create_user(username="otro", password="Clave-Segura-2026!")
        otra_solicitud = Solicitud.objects.create(equipo=self.equipo, descripcion="Falla privada de otra persona", solicitante=otro_solicitante)
        intervencion = Intervencion.objects.create(solicitud=otra_solicitud, tecnico=otro_solicitante, diagnostico="Prueba", costo_mano_obra=Decimal("750.00"))
        RepuestoUsado.objects.create(intervencion=intervencion, descripcion="Componente", cantidad=Decimal("1"), costo_unitario=Decimal("125.00"))
        reporte = generar_reporte("reparar_reemplazar", self.autoridad, {})
        self.assertEqual(reporte["filas"][0]["Fallas"], 0)
        self.assertEqual(reporte["filas"][0]["Costo acumulado (Bs.)"], Decimal("0"))
