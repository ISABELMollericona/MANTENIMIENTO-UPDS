import os
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, call_command
from django.db import transaction
from django.utils import timezone

from apps.cuentas.models import Rol
from apps.equipos.models import CategoriaEquipo, Equipo, EstadoEquipo
from apps.intervenciones.models import Intervencion
from apps.preventivo.models import MantenimientoPreventivo
from apps.solicitudes.models import HistorialSolicitud, Solicitud
from apps.ubicaciones.models import Ambiente

# Un usuario por rol acordado. Los docentes no tienen cuenta.
USUARIOS = [
    ("admin.demo", "Administración", "administrador@upds.edu.bo", "Administrador", True),
    ("responsable.demo", "Responsable Demo", "responsable@upds.edu.bo", "Responsable de mantenimiento", False),
    ("tecnico.demo", "Técnico Demo", "tecnico@upds.edu.bo", "Técnico", False),
    ("jefe.demo", "Jefe de Carrera Demo", "jefe.carrera@upds.edu.bo", "Jefe de carrera", False),
    ("estudiante.demo", "Estudiante Demo", "estudiante@upds.edu.bo", "Estudiante", False),
]

# Alcance: solo laboratorios de computación.
LABORATORIOS = [
    ("Laboratorio de Computación 1", "Bloque A"),
    ("Laboratorio de Computación 2", "Bloque A"),
    ("Laboratorio de Computación 3", "Bloque B"),
]

# (nombre, descripción, es_periferico)
CATEGORIAS = [
    ("Computadora", "Computadoras de escritorio de los laboratorios.", False),
    ("Teclado", "Teclado asociado a una computadora.", True),
    ("Mouse", "Mouse asociado a una computadora.", True),
]

DOCENTES = ["Lic. Ana Rojas", "Ing. Carlos Méndez", "Lic. María Vargas", "Ing. Jorge Salazar"]
PROBLEMAS = [
    "La computadora no enciende.",
    "El teclado tiene varias teclas que no responden.",
    "El mouse no se mueve en la pantalla.",
    "La computadora se reinicia sola durante la clase.",
    "Pantalla azul al iniciar Windows.",
    "El mouse hace doble clic solo.",
    "La computadora está muy lenta y se congela.",
    "No reconoce memorias USB.",
]

COMPUTADORAS_POR_LABORATORIO = 4


class Command(BaseCommand):
    help = "Carga datos ficticios de demostración (solo laboratorios de computación) sin duplicar registros."

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("seed_roles", verbosity=0)
        password = os.getenv("DEMO_PASSWORD", "Demo-UPDS-2026!")
        roles = {rol.nombre: rol for rol in Rol.objects.select_related("grupo").all()}
        users = self._crear_usuarios(roles, password)
        laboratorios = self._crear_laboratorios(users["responsable.demo"])
        categorias = self._crear_categorias(users["responsable.demo"])
        computadoras = self._crear_equipos(laboratorios, categorias, users["responsable.demo"])
        solicitudes = self._crear_reportes(computadoras, users)
        self._crear_preventivos(laboratorios, users)
        self.stdout.write(self.style.SUCCESS(
            f"Datos demo listos: {len(laboratorios)} laboratorios, {Equipo.objects.filter(codigo__startswith='LAB').count()} equipos "
            f"(computadoras con teclado y mouse), {len(solicitudes)} reportes de falla."
        ))
        self.stdout.write("Usuarios: " + ", ".join(u[0] for u in USUARIOS))
        self.stdout.write("Contraseña inicial común: la de DEMO_PASSWORD (por defecto Demo-UPDS-2026!). Se pide cambiarla al primer acceso.")

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

    def _crear_laboratorios(self, responsable):
        laboratorios = []
        for nombre, bloque in LABORATORIOS:
            laboratorio, _ = Ambiente.objects.get_or_create(
                nombre=nombre,
                bloque=bloque,
                defaults={"tipo": Ambiente.Tipo.LABORATORIO, "responsable": responsable, "creado_por": responsable},
            )
            laboratorios.append(laboratorio)
        return laboratorios

    def _crear_categorias(self, creador):
        categorias = {}
        for nombre, descripcion, es_periferico in CATEGORIAS:
            categoria, _ = CategoriaEquipo.objects.get_or_create(
                nombre=nombre,
                defaults={"descripcion": descripcion, "es_periferico": es_periferico, "creado_por": creador},
            )
            categorias[nombre] = categoria
        return categorias

    def _crear_equipos(self, laboratorios, categorias, responsable):
        operativo = EstadoEquipo.del_tipo(EstadoEquipo.Tipo.OPERATIVO)
        computadoras = []
        hoy = date.today()
        for numero_lab, laboratorio in enumerate(laboratorios, start=1):
            for numero in range(1, COMPUTADORAS_POR_LABORATORIO + 1):
                codigo = f"LAB{numero_lab}-PC{numero:02d}"
                indice = (numero_lab - 1) * COMPUTADORAS_POR_LABORATORIO + numero
                pc, creado = Equipo.objects.get_or_create(
                    codigo=codigo,
                    defaults={
                        "categoria": categorias["Computadora"],
                        "marca": ["Dell", "HP", "Lenovo"][indice % 3],
                        "modelo": ["OptiPlex 3080", "ProDesk 400", "ThinkCentre M70"][indice % 3],
                        "numero_serie": f"SN-PC-{indice:04d}",
                        "fecha_compra": hoy - timedelta(days=365 * (1 + indice % 6)),
                        "ambiente": laboratorio,
                        "estado": operativo,
                        "creado_por": responsable,
                    },
                )
                computadoras.append(pc)
                for categoria, sufijo, marca in ((categorias["Teclado"], "TEC", "Logitech"), (categorias["Mouse"], "MOU", "Genius")):
                    Equipo.objects.get_or_create(
                        codigo=f"{codigo}-{sufijo}",
                        defaults={
                            "categoria": categoria,
                            "marca": marca,
                            "modelo": "Estándar USB",
                            "numero_serie": f"SN-{sufijo}-{indice:04d}",
                            "fecha_compra": pc.fecha_compra,
                            "ambiente": laboratorio,
                            "equipo_principal": pc,
                            "estado": operativo,
                            "creado_por": responsable,
                        },
                    )
        # Un equipo obsoleto retirado (con sus periféricos): uno informado a Vicerrectoría y otro pendiente.
        baja = EstadoEquipo.del_tipo(EstadoEquipo.Tipo.BAJA)
        retirado = computadoras[-1]
        if not retirado.esta_de_baja:
            for equipo in [retirado, *retirado.perifericos.all()]:
                equipo.estado = baja
                equipo.fecha_baja = hoy - timedelta(days=20)
                equipo.motivo_baja = "Equipo obsoleto: no soporta el software de las materias."
                equipo.informado_vicerrectoria = equipo.pk == retirado.pk
                equipo.fecha_informe_vicerrectoria = hoy - timedelta(days=15) if equipo.pk == retirado.pk else None
                equipo._usuario_actualizacion = responsable
                equipo.save()
        return computadoras

    def _crear_reportes(self, computadoras, users):
        jefe, tecnico, responsable = users["jefe.demo"], users["tecnico.demo"], users["responsable.demo"]
        en_reparacion = EstadoEquipo.del_tipo(EstadoEquipo.Tipo.REPARACION)
        hoy = timezone.localdate()
        flujo = [Solicitud.Estado.REGISTRADA, Solicitud.Estado.ASIGNADA, Solicitud.Estado.EN_REPARACION, Solicitud.Estado.RESUELTA, Solicitud.Estado.RESUELTA, Solicitud.Estado.REGISTRADA, Solicitud.Estado.RESUELTA, Solicitud.Estado.CANCELADA]
        solicitudes = []
        for indice, estado in enumerate(flujo):
            pc = computadoras[indice % (len(computadoras) - 1)]
            # Algunas fallas son del teclado o del mouse de la computadora.
            equipo = pc
            if "teclado" in PROBLEMAS[indice].lower():
                equipo = pc.perifericos.filter(categoria__nombre="Teclado").first() or pc
            elif "mouse" in PROBLEMAS[indice].lower():
                equipo = pc.perifericos.filter(categoria__nombre="Mouse").first() or pc
            reportado = timezone.now() - timedelta(days=40 - indice * 4)
            solicitud = Solicitud.objects.filter(equipo=equipo, descripcion=PROBLEMAS[indice]).first()
            if solicitud is None:
                solicitud = Solicitud.objects.create(
                    equipo=equipo,
                    docente_solicitante=DOCENTES[indice % len(DOCENTES)],
                    descripcion=PROBLEMAS[indice],
                    prioridad=[Solicitud.Prioridad.ALTA, Solicitud.Prioridad.MEDIA, Solicitud.Prioridad.BAJA][indice % 3],
                    estado=estado,
                    solicitante=jefe,
                    tecnico_asignado=tecnico if estado != Solicitud.Estado.REGISTRADA else None,
                    fecha_reporte=reportado,
                    fecha_cierre=reportado + timedelta(days=6) if estado in {Solicitud.Estado.RESUELTA, Solicitud.Estado.CANCELADA} else None,
                    motivo_cancelacion="El docente informó que era un problema del proyector." if estado == Solicitud.Estado.CANCELADA else "",
                    creado_por=jefe,
                )
                if estado != Solicitud.Estado.REGISTRADA:
                    HistorialSolicitud.objects.create(solicitud=solicitud, estado_anterior=Solicitud.Estado.REGISTRADA, estado_nuevo=estado, usuario=responsable, comentario="Dato de demostración.")
                if estado in {Solicitud.Estado.EN_REPARACION, Solicitud.Estado.RESUELTA}:
                    salida = reportado.date() + timedelta(days=1)
                    devolucion = salida + timedelta(days=2 + indice) if estado == Solicitud.Estado.RESUELTA else None
                    devolucion = min(devolucion, hoy) if devolucion else None
                    Intervencion.objects.create(
                        solicitud=solicitud,
                        tecnico=tecnico,
                        laboratorio_origen=equipo.ambiente,
                        fecha_salida=salida,
                        fecha_devolucion=devolucion,
                        diagnostico=f"Revisión de: {PROBLEMAS[indice].lower()}",
                        trabajo_realizado="Se reemplazó la pieza dañada y se probó el equipo." if devolucion else "",
                        repuestos_usados="Fuente de poder 500 W" if devolucion and equipo.categoria.nombre == "Computadora" else "",
                        resultado=Intervencion.Resultado.REPARADO if devolucion else "",
                        creado_por=tecnico,
                    )
                    if estado == Solicitud.Estado.EN_REPARACION:
                        equipo.estado = en_reparacion
                        equipo._usuario_actualizacion = tecnico
                        equipo.save()
            solicitudes.append(solicitud)
        return solicitudes

    def _crear_preventivos(self, laboratorios, users):
        hoy = timezone.localdate()
        anio = hoy.year
        fechas = [date(anio, 2, 20), date(anio, 7, 15), date(anio, 11, 25)]
        for indice, laboratorio in enumerate(laboratorios):
            # 3 mantenimientos para el primero; 2 para los demás.
            for numero, fecha in enumerate(fechas[: 3 if indice == 0 else 2], start=1):
                realizado = fecha < hoy
                MantenimientoPreventivo.objects.get_or_create(
                    laboratorio=laboratorio,
                    anio=anio,
                    numero=numero,
                    defaults={
                        "fecha_programada": fecha,
                        "tecnico": users["tecnico.demo"],
                        "estado": MantenimientoPreventivo.Estado.REALIZADO if realizado else MantenimientoPreventivo.Estado.PENDIENTE,
                        "fecha_realizada": fecha if realizado else None,
                        "observaciones": "Limpieza interna, actualización de software y revisión de periféricos." if realizado else "",
                        "creado_por": users["responsable.demo"],
                    },
                )
