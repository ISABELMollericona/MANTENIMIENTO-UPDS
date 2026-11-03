from datetime import date
from decimal import Decimal

from django.db.models import Count, F, Q, Sum

from apps.cuentas.models import Usuario
from apps.equipos.models import Equipo
from apps.intervenciones.models import Intervencion, RepuestoUsado
from apps.preventivo.models import MantenimientoProgramado
from apps.solicitudes.models import Solicitud
from apps.ubicaciones.models import Ambiente

DEFINICIONES_REPORTES = [
    ("equipos_por_ambiente", "Equipos por ambiente"),
    ("equipos_fuera_servicio", "Equipos fuera de servicio"),
    ("solicitudes", "Solicitudes pendientes y atendidas"),
    ("historial_equipo", "Historial de mantenimiento por equipo"),
    ("equipos_mas_fallas", "Equipos con más fallas"),
    ("costos_periodo", "Mantenimientos por periodo y costos"),
    ("reparar_reemplazar", "Sugerencia: reparar o reemplazar"),
]


def _fecha(valor):
    try:
        return date.fromisoformat(valor) if valor else None
    except ValueError:
        return None


def _filtrar_equipo(queryset, filtros):
    desde, hasta = _fecha(filtros.get("desde")), _fecha(filtros.get("hasta"))
    if filtros.get("ambiente"):
        queryset = queryset.filter(ambiente_id=filtros["ambiente"])
    if filtros.get("categoria"):
        queryset = queryset.filter(categoria_id=filtros["categoria"])
    if desde:
        queryset = queryset.filter(creado_en__date__gte=desde)
    if hasta:
        queryset = queryset.filter(creado_en__date__lte=hasta)
    return queryset


def _solicitudes_visibles(usuario):
    queryset = Solicitud.objects.select_related("equipo", "equipo__categoria", "equipo__ambiente", "solicitante", "tecnico_asignado")
    if usuario.is_superuser or usuario.has_perm("cuentas.ver_todas_solicitudes"):
        return queryset
    return queryset.filter(Q(solicitante=usuario) | Q(tecnico_asignado=usuario))


def _filtrar_solicitudes(queryset, filtros):
    desde, hasta = _fecha(filtros.get("desde")), _fecha(filtros.get("hasta"))
    if filtros.get("ambiente"):
        queryset = queryset.filter(equipo__ambiente_id=filtros["ambiente"])
    if filtros.get("categoria"):
        queryset = queryset.filter(equipo__categoria_id=filtros["categoria"])
    if desde:
        queryset = queryset.filter(fecha_reporte__date__gte=desde)
    if hasta:
        queryset = queryset.filter(fecha_reporte__date__lte=hasta)
    return queryset


def _intervenciones_visibles(usuario, filtros):
    queryset = Intervencion.objects.select_related("solicitud__equipo", "solicitud__equipo__categoria", "solicitud__equipo__ambiente", "tecnico").prefetch_related("repuestos")
    if filtros.get("ambiente"):
        queryset = queryset.filter(solicitud__equipo__ambiente_id=filtros["ambiente"])
    if filtros.get("categoria"):
        queryset = queryset.filter(solicitud__equipo__categoria_id=filtros["categoria"])
    desde, hasta = _fecha(filtros.get("desde")), _fecha(filtros.get("hasta"))
    if desde:
        queryset = queryset.filter(fecha_inicio__date__gte=desde)
    if hasta:
        queryset = queryset.filter(fecha_inicio__date__lte=hasta)
    if not (usuario.is_superuser or usuario.has_perm("cuentas.ver_todas_solicitudes")):
        queryset = queryset.filter(Q(solicitud__solicitante=usuario) | Q(solicitud__tecnico_asignado=usuario))
    return queryset


def _costo_por_equipo(equipos, usuario):
    ids = list(equipos.values_list("pk", flat=True))
    intervenciones = Intervencion.objects.filter(solicitud__equipo_id__in=ids)
    repuestos_usados = RepuestoUsado.objects.filter(intervencion__solicitud__equipo_id__in=ids)
    if not (usuario.is_superuser or usuario.has_perm("cuentas.ver_todas_solicitudes")):
        alcance = Q(solicitud__solicitante=usuario) | Q(solicitud__tecnico_asignado=usuario)
        intervenciones = intervenciones.filter(alcance)
        repuestos_usados = repuestos_usados.filter(Q(intervencion__solicitud__solicitante=usuario) | Q(intervencion__solicitud__tecnico_asignado=usuario))
    mano_obra = dict(
        intervenciones
        .values("solicitud__equipo_id")
        .annotate(total=Sum("costo_mano_obra"))
        .values_list("solicitud__equipo_id", "total")
    )
    repuestos = dict(
        repuestos_usados
        .values("intervencion__solicitud__equipo_id")
        .annotate(total=Sum(F("cantidad") * F("costo_unitario")))
        .values_list("intervencion__solicitud__equipo_id", "total")
    )
    return {pk: (mano_obra.get(pk) or Decimal("0")) + (repuestos.get(pk) or Decimal("0")) for pk in ids}


def generar_reporte(clave, usuario, filtros):
    nombre = dict(DEFINICIONES_REPORTES).get(clave)
    if not nombre:
        clave, nombre = DEFINICIONES_REPORTES[0]
    equipos = _filtrar_equipo(Equipo.objects.select_related("categoria", "ambiente", "responsable"), filtros)
    solicitudes = _filtrar_solicitudes(_solicitudes_visibles(usuario), filtros)
    intervenciones = _intervenciones_visibles(usuario, filtros)

    if clave == "equipos_por_ambiente":
        conteo = {}
        for equipo in equipos:
            nombre_ambiente = equipo.ambiente.nombre if equipo.ambiente else "Sin ambiente"
            conteo[nombre_ambiente] = conteo.get(nombre_ambiente, 0) + 1
        headers = ["Ambiente", "Cantidad de equipos"]
        filas = [{"Ambiente": nombre, "Cantidad de equipos": cantidad} for nombre, cantidad in sorted(conteo.items())]
    elif clave == "equipos_fuera_servicio":
        filas_equipo = equipos.filter(estado=Equipo.Estado.FUERA_DE_SERVICIO)
        headers = ["Código", "Categoría", "Marca", "Modelo", "Ambiente", "Responsable"]
        filas = [{"Código": e.codigo, "Categoría": e.categoria.nombre, "Marca": e.marca, "Modelo": e.modelo, "Ambiente": e.ambiente.nombre if e.ambiente else "Sin ambiente", "Responsable": str(e.responsable or "Sin asignar")} for e in filas_equipo]
    elif clave == "solicitudes":
        headers = ["N.º", "Equipo", "Descripción", "Prioridad", "Estado", "Solicitante", "Técnico", "Fecha"]
        filas = [{"N.º": s.pk, "Equipo": s.equipo.codigo, "Descripción": s.descripcion, "Prioridad": s.get_prioridad_display(), "Estado": s.get_estado_display(), "Solicitante": str(s.solicitante), "Técnico": str(s.tecnico_asignado or "Sin asignar"), "Fecha": s.fecha_reporte.strftime("%d/%m/%Y")} for s in solicitudes.order_by("-fecha_reporte")]
    elif clave == "historial_equipo":
        headers = ["Equipo", "Solicitud", "Intervención", "Diagnóstico", "Trabajo realizado", "Técnico", "Costo (Bs.)", "Inicio", "Fin"]
        filas = [{"Equipo": i.solicitud.equipo.codigo, "Solicitud": i.solicitud.pk, "Intervención": i.pk, "Diagnóstico": i.diagnostico, "Trabajo realizado": i.trabajo_realizado, "Técnico": str(i.tecnico), "Costo (Bs.)": i.costo_total, "Inicio": i.fecha_inicio.strftime("%d/%m/%Y"), "Fin": i.fecha_fin.strftime("%d/%m/%Y") if i.fecha_fin else "En curso"} for i in intervenciones.order_by("-fecha_inicio")]
    elif clave == "equipos_mas_fallas":
        conteos = dict(solicitudes.values("equipo_id").annotate(total=Count("pk")).values_list("equipo_id", "total"))
        headers = ["Código", "Equipo", "Ambiente", "Número de fallas"]
        filas = [{"Código": e.codigo, "Equipo": f"{e.marca} {e.modelo}".strip(), "Ambiente": e.ambiente.nombre if e.ambiente else "Sin ambiente", "Número de fallas": conteos.get(e.pk, 0)} for e in equipos]
        filas.sort(key=lambda fila: (-fila["Número de fallas"], fila["Código"]))
        filas = filas[:50]
    elif clave == "costos_periodo":
        headers = ["Equipo", "Solicitud", "Técnico", "Inicio", "Mano de obra (Bs.)", "Total intervención (Bs.)"]
        filas = [{"Equipo": i.solicitud.equipo.codigo, "Solicitud": i.solicitud.pk, "Técnico": str(i.tecnico), "Inicio": i.fecha_inicio.strftime("%d/%m/%Y"), "Mano de obra (Bs.)": i.costo_mano_obra, "Total intervención (Bs.)": i.costo_total} for i in intervenciones.order_by("-fecha_inicio")]
        filas.append({"Equipo": "TOTAL", "Solicitud": "", "Técnico": "", "Inicio": "", "Mano de obra (Bs.)": sum((fila["Mano de obra (Bs.)"] for fila in filas), Decimal("0")), "Total intervención (Bs.)": sum((fila["Total intervención (Bs.)"] for fila in filas), Decimal("0"))})
    else:
        costos = _costo_por_equipo(equipos, usuario)
        conteos = dict(solicitudes.values("equipo_id").annotate(total=Count("pk")).values_list("equipo_id", "total"))
        headers = ["Código", "Equipo", "Antigüedad", "Fallas", "Costo acumulado (Bs.)", "Costo de compra (Bs.)", "Sugerencia"]
        filas = []
        for equipo in equipos:
            antiguedad = f"{(date.today() - equipo.fecha_compra).days // 365} años" if equipo.fecha_compra else "Sin dato"
            costo = costos.get(equipo.pk, Decimal("0"))
            sugerencia = "Sin datos suficientes"
            if equipo.costo_compra is not None:
                from django.conf import settings

                sugerencia = "Evaluar reemplazo" if costo >= equipo.costo_compra * Decimal(str(settings.REPAIR_REPLACE_THRESHOLD)) else "Reparación bajo umbral"
            filas.append({"Código": equipo.codigo, "Equipo": f"{equipo.marca} {equipo.modelo}".strip(), "Antigüedad": antiguedad, "Fallas": conteos.get(equipo.pk, 0), "Costo acumulado (Bs.)": costo, "Costo de compra (Bs.)": equipo.costo_compra if equipo.costo_compra is not None else "Sin dato", "Sugerencia": sugerencia})
        filas.sort(key=lambda fila: (-fila["Fallas"], fila["Código"]))

    return {"clave": clave, "nombre": nombre, "headers": headers, "filas": filas}