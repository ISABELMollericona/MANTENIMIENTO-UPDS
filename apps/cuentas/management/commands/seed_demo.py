import os
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, call_command
from django.db import transaction
from django.utils import timezone

from apps.cuentas.models import Rol
from apps.equipos.models import CategoriaEquipo, Equipo
from apps.intervenciones.models import Intervencion, RepuestoUsado
from apps.preventivo.models import MantenimientoProgramado, PlanPreventivo
from apps.solicitudes.models import HistorialSolicitud, Solicitud
from apps.ubicaciones.models import Ambiente

USUARIOS = [
    ("admin.demo", "Administración", "administrador@upds.edu.bo", "Administrador", True),
    ("responsable.demo", "Responsable Demo", "responsable@upds.edu.bo", "Responsable de equipamiento", False),
    ("tecnico.demo", "Técnico Demo", "tecnico@upds.edu.bo", "Técnico", False),
    ("docente.demo", "Docente Demo", "docente@upds.edu.bo", "Solicitante", False),
    ("autoridad.demo", "Autoridad Demo", "autoridad@upds.edu.bo", "Autoridad", False),
]

AMBIENTES = [
    ("Laboratorio de Física", Ambiente.Tipo.LABORATORIO, "Bloque A"),
    ("Laboratorio de Informática 1", Ambiente.Tipo.LABORATORIO, "Bloque A"),
    ("Laboratorio de Informática 2", Ambiente.Tipo.LABORATORIO, "Bloque B"),
    ("Aula 101", Ambiente.Tipo.AULA, "Bloque A"),
    ("Aula 204", Ambiente.Tipo.AULA, "Bloque B"),
    ("Sala Audiovisual", Ambiente.Tipo.SALA_AUDIOVISUAL, "Bloque Central"),
    ("Oficina Académica", Ambiente.Tipo.OFICINA, "Bloque Central"),
    ("Oficina Administrativa", Ambiente.Tipo.OFICINA, "Bloque Administrativo"),
]

CATEGORIAS = [
    ("Computadora", "Equipos de escritorio y portátiles."),
    ("Proyector", "Proyectores y pantallas."),
    ("Impresora", "Impresoras y escáneres."),
    ("Audio", "Consolas, parlantes y micrófonos."),
    ("Mobiliario", "Mobiliario de aulas y oficinas."),
]

ESTADOS_EQUIPO = [
    Equipo.Estado.OPERATIVO,
    Equipo.Estado.OPERATIVO,
    Equipo.Estado.EN_MANTENIMIENTO,
    Equipo.Estado.FUERA_DE_SERVICIO,
    Equipo.Estado.DADO_DE_BAJA,
]
ESTADOS_SOLICITUD = [
    Solicitud.Estado.REGISTRADA,
    Solicitud.Estado.ASIGNADA,
    Solicitud.Estado.EN_REPARACION,
    Solicitud.Estado.RESUELTA,
    Solicitud.Estado.CANCELADA,
]


class Command(BaseCommand):
    help = "Carga datos ficticios de demostración sin duplicar registros."

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("seed_roles", verbosity=0)
        password = os.getenv("DEMO_PASSWORD", "Demo-UPDS-2026!")
        roles = {rol.nombre: rol for rol in Rol.objects.select_related("grupo").all()}
        users = self._crear_usuarios(roles, password)
        ambientes = self._crear_ambientes(users["responsable.demo"])
        categorias = self._crear_categorias(users["responsable.demo"])
        equipos = self._crear_equipos(ambientes, categorias, users)
        solicitudes = self._crear_solicitudes(equipos, users)
        self._crear_intervenciones(solicitudes, users)
        self._crear_preventivos(equipos, categorias, users)
        self.stdout.write(self.style.SUCCESS(
            f"Datos demo listos: {len(ambientes)} ambientes, {len(categorias)} categorías, "
            f"{len(equipos)} equipos, {len(solicitudes)} solicitudes."
        ))
        self.stdout.write("Usuarios: admin.demo, responsable.demo, tecnico.demo, docente.demo, autoridad.demo")
        self.stdout.write("Contraseña inicial común: Demo-UPDS-2026! (o la indicada en DEMO_PASSWORD)")

    def _crear_usuarios(self, roles, password):
        usuario_modelo = get_user_model()
        resultado = {}
        for username, nombre, email, nombre_rol, admin in USUARIOS:
            usuario = usuario_modelo.objects.filter(username=username).first()
            if usuario is None:
                nombres = nombre.split(" ", 1)
                usuario = usuario_modelo.objects.create_user(
                    username=username,
                    email=email,
                    first_name=nombres[0],
                    last_name=nombres[1] if len(nombres) > 1 else "",
                    password=password,
                    is_staff=admin,
                    is_superuser=admin,
                    force_password_change=True,
                )
            usuario.groups.add(roles[nombre_rol].grupo)
            resultado[username] = usuario
        return resultado

    def _crear_ambientes(self, responsable):
        ambientes = []
        for nombre, tipo, bloque in AMBIENTES:
            ambiente, _ = Ambiente.objects.get_or_create(
                nombre=nombre,
                bloque=bloque,
                defaults={"tipo": tipo, "responsable": responsable, "creado_por": responsable},
            )
            ambientes.append(ambiente)
        return ambientes

    def _crear_categorias(self, creador):
        categorias = []
        for nombre, descripcion in CATEGORIAS:
            categoria, _ = CategoriaEquipo.objects.get_or_create(
                nombre=nombre,
                defaults={"descripcion": descripcion, "creado_por": creador},
            )
            categorias.append(categoria)
        return categorias

    def _crear_equipos(self, ambientes, categorias, users):
        equipos = []
        fecha_base = date.today()
        for indice in range(40):
            ambiente = ambientes[indice // 5]
            categoria = categorias[indice % len(categorias)]
            codigo = f"DEMO-{indice + 1:03d}"
            equipo, _ = Equipo.objects.get_or_create(
                codigo=codigo,
                defaults={
                    "categoria": categoria,
                    "marca": ["Lenovo", "Epson", "HP", "Sony", "Dell"][indice % 5],
                    "modelo": f"Modelo-{indice % 7 + 1}",
                    "numero_serie": f"SN-DEMO-{indice + 1:04d}",
                    "fecha_compra": fecha_base - timedelta(days=365 * (1 + indice % 8)),
                    "costo_compra": Decimal(800 + (indice % 12) * 175),
                    "ambiente": ambiente,
                    "responsable": users["responsable.demo"],
                    "estado": ESTADOS_EQUIPO[indice % len(ESTADOS_EQUIPO)],
                    "observaciones": "Equipo ficticio para demostración.",
                    "creado_por": users["responsable.demo"],
                },
            )
            equipos.append(equipo)
        return equipos

    def _crear_solicitudes(self, equipos, users):
        solicitudes = []
        ahora = timezone.now()
        solicitantes = [users["docente.demo"], users["responsable.demo"]]
        tecnico = users["tecnico.demo"]
        for indice in range(25):
            estado = ESTADOS_SOLICITUD[indice % len(ESTADOS_SOLICITUD)]
            fecha_reporte = ahora - timedelta(days=indice + 1)
            cerrada = estado in {Solicitud.Estado.RESUELTA, Solicitud.Estado.CANCELADA}
            defaults = {
                "descripcion": f"Solicitud ficticia {indice + 1}: requiere revisión de funcionamiento.",
                "prioridad": [Solicitud.Prioridad.ALTA, Solicitud.Prioridad.MEDIA, Solicitud.Prioridad.BAJA][indice % 3],
                "estado": estado,
                "solicitante": solicitantes[indice % len(solicitantes)],
                "tecnico_asignado": tecnico if estado != Solicitud.Estado.REGISTRADA else None,
                "fecha_reporte": fecha_reporte,
                "fecha_cierre": fecha_reporte + timedelta(hours=5) if cerrada else None,
                "motivo_cancelacion": "Solicitud duplicada de demostración." if estado == Solicitud.Estado.CANCELADA else "",
                "creado_por": solicitantes[indice % len(solicitantes)],
            }
            solicitud, creada = Solicitud.objects.get_or_create(equipo=equipos[indice], descripcion=defaults["descripcion"], defaults=defaults)
            if creada and estado != Solicitud.Estado.REGISTRADA:
                HistorialSolicitud.objects.create(
                    solicitud=solicitud,
                    estado_anterior=Solicitud.Estado.REGISTRADA,
                    estado_nuevo=estado,
                    usuario=users["responsable.demo"] if estado == Solicitud.Estado.ASIGNADA else tecnico,
                    comentario="Estado inicial de demostración.",
                )
            solicitudes.append(solicitud)
        return solicitudes

    def _crear_intervenciones(self, solicitudes, users):
        tecnico = users["tecnico.demo"]
        for indice, solicitud in enumerate(solicitudes):
            if solicitud.estado not in {Solicitud.Estado.EN_REPARACION, Solicitud.Estado.RESUELTA}:
                continue
            fecha_inicio = solicitud.fecha_reporte + timedelta(hours=1)
            cerrada = solicitud.estado == Solicitud.Estado.RESUELTA
            intervencion, creada = Intervencion.objects.get_or_create(
                solicitud=solicitud,
                diagnostico="Revisión de demostración del equipo.",
                defaults={
                    "tecnico": tecnico,
                    "trabajo_realizado": "Ajuste y prueba funcional." if cerrada else "Diagnóstico iniciado.",
                    "fecha_inicio": fecha_inicio,
                    "fecha_fin": fecha_inicio + timedelta(hours=2) if cerrada else None,
                    "costo_mano_obra": Decimal(60 + indice * 5),
                    "resultado": Intervencion.Resultado.REPARADO if cerrada else "",
                    "observaciones": "Intervención ficticia de demostración.",
                    "creado_por": tecnico,
                },
            )
            if creada:
                RepuestoUsado.objects.get_or_create(
                    intervencion=intervencion,
                    descripcion="Cable de conexión de demostración",
                    defaults={"cantidad": Decimal("1.00"), "costo_unitario": Decimal("25.00")},
                )

    def _crear_preventivos(self, equipos, categorias, users):
        planes = []
        for indice, categoria in enumerate(categorias):
            plan, _ = PlanPreventivo.objects.get_or_create(
                categoria=categoria,
                nombre=f"Inspección periódica de {categoria.nombre}",
                defaults={
                    "periodicidad_meses": 6 if indice % 2 == 0 else 12,
                    "actividades": "Limpieza, inspección visual y prueba funcional.",
                    "creado_por": users["responsable.demo"],
                },
            )
            planes.append(plan)

        hoy = timezone.localdate()
        for indice, equipo in enumerate(equipos[:20]):
            plan = next(item for item in planes if item.categoria_id == equipo.categoria_id)
            fecha = hoy + timedelta(days=(indice - 4) * 12)
            MantenimientoProgramado.objects.get_or_create(
                equipo=equipo,
                plan=plan,
                fecha_programada=fecha,
                defaults={
                    "tecnico": users["tecnico.demo"],
                    "creado_por": users["responsable.demo"],
                    "observaciones": "Mantenimiento programado para datos de demostración.",
                },
            )