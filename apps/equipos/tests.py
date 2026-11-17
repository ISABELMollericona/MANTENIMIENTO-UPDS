from datetime import date, timedelta

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import Rol, Usuario
from apps.ubicaciones.models import Ambiente

from .models import CategoriaEquipo, Equipo, EstadoEquipo


class EquiposTests(TestCase):
    def setUp(self):
        call_command("seed_roles", verbosity=0)
        self.rol = Rol.objects.get(nombre="Responsable de mantenimiento")
        self.usuario = Usuario.objects.create_user(username="gestor", password="Clave-Segura-2026!")
        self.usuario.groups.add(self.rol.grupo)
        self.ambiente = Ambiente.objects.create(nombre="Laboratorio 1", tipo="laboratorio", bloque="A")
        self.categoria = CategoriaEquipo.objects.create(nombre="Computadora")
        self.teclado = CategoriaEquipo.objects.create(nombre="Teclado", es_periferico=True)
        self.operativo = EstadoEquipo.del_tipo(EstadoEquipo.Tipo.OPERATIVO)
        self.reparacion = EstadoEquipo.del_tipo(EstadoEquipo.Tipo.REPARACION)
        self.baja = EstadoEquipo.del_tipo(EstadoEquipo.Tipo.BAJA)
        self.equipo = Equipo.objects.create(codigo="EQ-001", categoria=self.categoria, ambiente=self.ambiente, creado_por=self.usuario)
        self.client.force_login(self.usuario)

    def _datos_equipo(self, **extra):
        datos = {
            "codigo": "EQ-NUEVO", "categoria": self.categoria.pk, "marca": "Dell", "modelo": "OptiPlex", "numero_serie": "SN1",
            "fecha_compra": "2024-01-15", "ambiente": self.ambiente.pk, "equipo_principal": "", "estado": self.operativo.pk,
            "responsable": "", "observaciones": "",
        }
        datos.update(extra)
        return datos

    def test_estados_iniciales_son_los_del_cliente_y_estan_en_tabla(self):
        self.assertEqual(
            list(EstadoEquipo.objects.values_list("nombre", flat=True)),
            ["Operativo", "En mantenimiento/reparación", "Obsoleto/Dado de baja"],
        )
        self.assertEqual(self.equipo.estado, self.operativo)

    def test_estado_editable_cambia_el_nombre_en_todos_los_equipos(self):
        respuesta = self.client.post(reverse("equipos:estado_editar", args=[self.operativo.pk]), {"nombre": "Disponible", "tipo": "operativo", "orden": 1, "activo": "on"})
        self.assertRedirects(respuesta, reverse("equipos:estados"))
        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.estado.nombre, "Disponible")

    def test_no_se_puede_dejar_un_tipo_sin_estado_activo(self):
        respuesta = self.client.post(reverse("equipos:estado_editar", args=[self.baja.pk]), {"nombre": self.baja.nombre, "tipo": "baja", "orden": 3})
        self.assertEqual(respuesta.status_code, 200)
        self.baja.refresh_from_db()
        self.assertTrue(self.baja.activo)

    def test_cambiar_laboratorio_y_estado_registra_quien_y_cuando(self):
        segundo = Ambiente.objects.create(nombre="Laboratorio 2", tipo="laboratorio", bloque="B")
        self.equipo.ambiente = segundo
        self.equipo.estado = self.reparacion
        self.equipo._usuario_actualizacion = self.usuario
        self.equipo.save()
        cambios = list(self.equipo.historial.values_list("campo_cambiado", "usuario__username", "valor_nuevo"))
        self.assertEqual({campo for campo, _, _ in cambios}, {"ambiente", "estado"})
        self.assertTrue(all(usuario == "gestor" for _, usuario, _ in cambios))
        self.assertIn(("estado", "gestor", "En mantenimiento/reparación"), cambios)
        self.assertIsNotNone(self.equipo.historial.get(campo_cambiado="estado").fecha)

    def test_registrar_equipo_con_todos_los_campos(self):
        respuesta = self.client.post(reverse("equipos:crear"), self._datos_equipo())
        self.assertRedirects(respuesta, reverse("equipos:lista"))
        equipo = Equipo.objects.get(codigo="EQ-NUEVO")
        self.assertEqual((equipo.marca, equipo.modelo, equipo.numero_serie, equipo.fecha_compra, equipo.ambiente), ("Dell", "OptiPlex", "SN1", date(2024, 1, 15), self.ambiente))

    def test_campos_obligatorios_y_fecha_de_compra_futura(self):
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        respuesta = self.client.post(reverse("equipos:crear"), self._datos_equipo(codigo="", ambiente="", fecha_compra=manana))
        self.assertEqual(respuesta.status_code, 200)
        errores = respuesta.context["form"].errors
        self.assertIn("codigo", errores)
        self.assertIn("ambiente", errores)
        self.assertIn("fecha_compra", errores)

    def test_periferico_se_asocia_a_una_computadora(self):
        respuesta = self.client.post(reverse("equipos:crear"), self._datos_equipo(codigo="EQ-001-TEC", categoria=self.teclado.pk, equipo_principal=self.equipo.pk))
        self.assertRedirects(respuesta, reverse("equipos:lista"))
        self.assertEqual(list(self.equipo.perifericos.values_list("codigo", flat=True)), ["EQ-001-TEC"])

    def test_computadora_no_puede_ser_periferico(self):
        otra = Equipo.objects.create(codigo="EQ-002", categoria=self.categoria, ambiente=self.ambiente)
        respuesta = self.client.post(reverse("equipos:editar", args=[otra.pk]), self._datos_equipo(codigo="EQ-002", equipo_principal=self.equipo.pk))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("equipo_principal", respuesta.context["form"].errors)

    def test_lista_filtra_y_ficha_no_muestra_costos(self):
        self.equipo.marca, self.equipo.modelo = "Dell", "OptiPlex"
        self.equipo.save()
        respuesta = self.client.get(reverse("equipos:lista"), {"q": "OptiPlex", "ambiente": self.ambiente.pk, "estado": self.operativo.pk})
        self.assertContains(respuesta, "EQ-001")
        ficha = self.client.get(reverse("equipos:ficha", args=[self.equipo.pk]))
        self.assertEqual(ficha.status_code, 200)
        self.assertNotContains(ficha, "Bs.")
        self.assertNotContains(ficha, "Costo")

    def test_baja_registra_motivo_y_vicerrectoria_con_sus_perifericos(self):
        periferico = Equipo.objects.create(codigo="EQ-001-MOU", categoria=self.teclado, ambiente=self.ambiente, equipo_principal=self.equipo)
        hoy = timezone.localdate().isoformat()
        respuesta = self.client.post(reverse("equipos:baja", args=[self.equipo.pk]), {
            "estado": self.baja.pk, "fecha_baja": hoy, "motivo_baja": "Obsoleto",
            "informado_vicerrectoria": "on", "fecha_informe_vicerrectoria": hoy, "incluir_perifericos": "on",
        })
        self.assertRedirects(respuesta, reverse("equipos:ficha", args=[self.equipo.pk]))
        self.equipo.refresh_from_db()
        periferico.refresh_from_db()
        self.assertTrue(self.equipo.esta_de_baja and periferico.esta_de_baja)
        self.assertTrue(self.equipo.informado_vicerrectoria)
        self.assertEqual(self.equipo.historial.filter(campo_cambiado="estado").count(), 1)
        bajas = self.client.get(reverse("equipos:bajas"))
        self.assertContains(bajas, "EQ-001")
        self.assertContains(bajas, "EQ-001-MOU")

    def test_baja_exige_motivo_y_fecha_de_informe_si_se_marca_informado(self):
        respuesta = self.client.post(reverse("equipos:baja", args=[self.equipo.pk]), {"estado": self.baja.pk, "fecha_baja": timezone.localdate().isoformat(), "motivo_baja": "", "informado_vicerrectoria": "on"})
        self.assertEqual(respuesta.status_code, 200)
        errores = respuesta.context["form"].errors
        self.assertIn("motivo_baja", errores)
        self.assertIn("fecha_informe_vicerrectoria", errores)
        self.equipo.refresh_from_db()
        self.assertFalse(self.equipo.esta_de_baja)

    def test_marcar_informado_despues_desde_bajas(self):
        self.equipo.estado, self.equipo.fecha_baja, self.equipo.motivo_baja = self.baja, timezone.localdate(), "Obsoleto"
        self.equipo.save()
        respuesta = self.client.post(reverse("equipos:informe_vicerrectoria", args=[self.equipo.pk]), {"informado_vicerrectoria": "on", "fecha_informe_vicerrectoria": timezone.localdate().isoformat()})
        self.assertRedirects(respuesta, reverse("equipos:bajas"))
        self.equipo.refresh_from_db()
        self.assertTrue(self.equipo.informado_vicerrectoria)
        self.assertTrue(self.equipo.historial.filter(campo_cambiado="vicerrectoria").exists())

    def test_sin_permiso_autorizacion_no_puede_dar_baja(self):
        self.rol.grupo.permissions.remove(Permission.objects.get(content_type__app_label="cuentas", codename="autorizar_baja_equipo"))
        respuesta = self.client.post(reverse("equipos:baja", args=[self.equipo.pk]))
        self.assertEqual(respuesta.status_code, 403)

    def test_edicion_normal_no_ofrece_estado_de_baja(self):
        respuesta = self.client.post(reverse("equipos:editar", args=[self.equipo.pk]), self._datos_equipo(codigo="EQ-001", estado=self.baja.pk))
        self.assertEqual(respuesta.status_code, 200)
        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.estado, self.operativo)

    def test_modelo_valida_informe_sin_marca(self):
        self.equipo.fecha_informe_vicerrectoria = timezone.localdate()
        with self.assertRaises(ValidationError):
            self.equipo.full_clean()

    def test_formularios_traen_la_fecha_de_hoy_por_defecto(self):
        from apps.preventivo.forms import MarcarRealizadoForm
        from apps.preventivo.models import MantenimientoPreventivo

        from .forms import BajaEquipoForm

        self.assertEqual(BajaEquipoForm(instance=self.equipo)["fecha_baja"].value(), timezone.localdate())
        mantenimiento = MantenimientoPreventivo(laboratorio=self.ambiente, anio=2026, numero=1, fecha_programada=date(2026, 1, 1))
        self.assertEqual(MarcarRealizadoForm(instance=mantenimiento)["fecha_realizada"].value(), timezone.localdate())
