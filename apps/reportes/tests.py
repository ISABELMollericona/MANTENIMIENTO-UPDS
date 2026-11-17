from datetime import date, timedelta

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import Rol, Usuario
from apps.equipos.models import CategoriaEquipo, Equipo, EstadoEquipo
from apps.intervenciones.models import Intervencion
from apps.preventivo.models import MantenimientoPreventivo
from apps.solicitudes.models import Solicitud
from apps.ubicaciones.models import Ambiente

from .services import DEFINICIONES_REPORTES, generar_reporte


class ReportesTests(TestCase):
    def setUp(self):
        call_command("seed_roles", verbosity=0)
        self.responsable = Usuario.objects.create_user(username="responsable", password="Clave-Segura-2026!")
        self.responsable.groups.add(Rol.objects.get(nombre="Responsable de mantenimiento").grupo)
        self.tecnico = Usuario.objects.create_user(username="tecnico", password="Clave-Segura-2026!")
        self.tecnico.groups.add(Rol.objects.get(nombre="Técnico").grupo)
        self.jefe = Usuario.objects.create_user(username="jefe", password="Clave-Segura-2026!")
        self.jefe.groups.add(Rol.objects.get(nombre="Jefe de carrera").grupo)
        self.lab = Ambiente.objects.create(nombre="Laboratorio 1", tipo="laboratorio", bloque="A")
        self.lab2 = Ambiente.objects.create(nombre="Laboratorio 2", tipo="laboratorio", bloque="B")
        computadora = CategoriaEquipo.objects.create(nombre="Computadora")
        self.hoy = timezone.localdate()
        self.pc = Equipo.objects.create(codigo="PC-01", categoria=computadora, marca="Dell", ambiente=self.lab, estado=EstadoEquipo.del_tipo("reparacion"))
        self.obsoleta = Equipo.objects.create(codigo="PC-02", categoria=computadora, ambiente=self.lab2, estado=EstadoEquipo.del_tipo("baja"), fecha_baja=self.hoy, motivo_baja="Obsoleta")
        Equipo.objects.create(codigo="PC-03", categoria=computadora, ambiente=self.lab)
        self.solicitud = Solicitud.objects.create(equipo=self.pc, docente_solicitante="Lic. Ana Rojas", descripcion="No enciende", solicitante=self.jefe, tecnico_asignado=self.tecnico, estado=Solicitud.Estado.RESUELTA)
        Solicitud.objects.create(equipo=self.pc, docente_solicitante="Ing. Méndez", descripcion="Se reinicia", solicitante=self.jefe)
        self.reparacion = Intervencion.objects.create(solicitud=self.solicitud, tecnico=self.tecnico, laboratorio_origen=self.lab, fecha_salida=self.hoy - timedelta(days=10), fecha_devolucion=self.hoy - timedelta(days=3), diagnostico="Fuente", trabajo_realizado="Cambio", repuestos_usados="Fuente 500 W", resultado="reparado")
        MantenimientoPreventivo.objects.create(laboratorio=self.lab, anio=self.hoy.year, numero=1, fecha_programada=date(self.hoy.year, 1, 20), tecnico=self.tecnico)
        self.client.force_login(self.responsable)

    def _filas(self, clave, **filtros):
        return generar_reporte(clave, self.responsable, filtros)["filas"]

    def test_estan_los_siete_reportes_del_cliente_y_se_renderizan(self):
        self.assertEqual([c for c, _ in DEFINICIONES_REPORTES], ["equipos_por_ambiente", "equipos_reparacion_obsoletos", "solicitudes", "historial_equipo", "tiempo_fuera", "equipos_mas_fallas", "mantenimientos_periodo"])
        for clave, nombre in DEFINICIONES_REPORTES:
            with self.subTest(reporte=clave):
                respuesta = self.client.get(reverse("reportes:lista"), {"reporte": clave, "equipo": self.pc.pk})
                self.assertContains(respuesta, nombre)
                self.assertNotContains(respuesta, "Costo")

    def test_equipos_por_laboratorio_cuenta_por_estado(self):
        filas = {fila["Laboratorio"]: fila for fila in self._filas("equipos_por_ambiente")}
        self.assertEqual(filas["Laboratorio 1"]["Total"], 2)
        self.assertEqual(filas["TOTAL"]["Total"], 3)

    def test_en_reparacion_y_obsoletos(self):
        codigos = [fila["Código"] for fila in self._filas("equipos_reparacion_obsoletos")]
        self.assertEqual(sorted(codigos), ["PC-01", "PC-02"])

    def test_reportes_pendientes_y_atendidos_con_docente(self):
        self.assertEqual(len(self._filas("solicitudes")), 2)
        self.assertEqual([f["Docente solicitante"] for f in self._filas("solicitudes", situacion="pendientes")], ["Ing. Méndez"])
        self.assertEqual([f["Docente solicitante"] for f in self._filas("solicitudes", situacion="atendidos")], ["Lic. Ana Rojas"])

    def test_historial_de_un_equipo(self):
        datos = generar_reporte("historial_equipo", self.responsable, {"equipo": str(self.pc.pk)})
        eventos = [fila["Evento"] for fila in datos["filas"]]
        self.assertTrue(any(e.startswith("Salida a reparación") for e in eventos))
        self.assertTrue(any(e.startswith("Devolución") for e in eventos))
        self.assertTrue(any(e.startswith("Reporte de falla") for e in eventos))
        self.assertIn("PC-01", datos["subtitulo"])

    def test_tiempo_fuera_es_devolucion_menos_salida(self):
        filas = self._filas("tiempo_fuera")
        self.assertEqual(filas[0]["Días fuera"], 7)
        self.assertEqual(filas[-1]["Días fuera"], 7.0)

    def test_equipos_con_mas_fallas(self):
        self.assertEqual(self._filas("equipos_mas_fallas")[0], {"Código": "PC-01", "Equipo": "Computadora Dell", "Laboratorio": "Laboratorio 1", "Número de fallas": 2})

    def test_mantenimientos_por_periodo_incluye_preventivos_y_reparaciones(self):
        tipos = {fila["Tipo"] for fila in self._filas("mantenimientos_periodo", desde=f"{self.hoy.year}-01-01", hasta=self.hoy.isoformat())}
        self.assertEqual(tipos, {"Preventivo", "Correctivo (reparación)"})

    def test_exportar_excel_y_pdf(self):
        for formato, tipo in (("excel", "spreadsheetml"), ("pdf", "pdf")):
            respuesta = self.client.get(reverse("reportes:lista"), {"reporte": "tiempo_fuera", "formato": formato})
            self.assertEqual(respuesta.status_code, 200)
            self.assertIn(tipo, respuesta["Content-Type"])

    def test_roles_sin_permiso_no_ven_reportes(self):
        for usuario in (self.tecnico, self.jefe):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(reverse("reportes:lista")).status_code, 403)
