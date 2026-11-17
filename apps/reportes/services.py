from datetime import date

from django.db.models import Count, Q
from django.utils import timezone

from apps.equipos.models import Equipo, EstadoEquipo
from apps.intervenciones.models import Intervencion
from apps.preventivo.models import MantenimientoPreventivo
from apps.solicitudes.models import Solicitud

# Los 7 reportes acordados con el cliente. Sin costos: están fuera del alcance.
DEFINICIONES_REPORTES = [
    ("equipos_por_ambiente", "Equipos por laboratorio"),
    ("equipos_reparacion_obsoletos", "Equipos en reparación y obsoletos"),
    ("solicitudes", "Reportes de falla pendientes y atendidos"),
    ("historial_equipo", "Historial de un equipo"),
    ("tiempo_fuera", "Tiempo que estuvo fuera cada equipo"),
    ("equipos_mas_fallas", "Equipos con más fallas"),
    ("mantenimientos_periodo", "Mantenimientos por periodo"),
]


def _fecha(valor):
    try:
        return date.fromisoformat(valor) if valor else None
    except ValueError:
        return None


def _id(valor):
    return int(valor) if str(valor or "").isdigit() else None


def _fmt(valor):
    return valor.strftime("%d/%m/%Y") if valor else ""


def _laboratorio(ambiente):
    return ambiente.nombre if ambiente else "Sin laboratorio"


def _filtrar_equipo(queryset, filtros, prefijo=""):
    if _id(filtros.get("ambiente")):
        queryset = queryset.filter(**{f"{prefijo}ambiente_id": _id(filtros["ambiente"])})
    if _id(filtros.get("categoria")):
        queryset = queryset.filter(**{f"{prefijo}categoria_id": _id(filtros["categoria"])})
    return queryset


def _solicitudes_visibles(usuario):
    queryset = Solicitud.objects.select_related("equipo", "equipo__categoria", "equipo__ambiente", "solicitante", "tecnico_asignado")
    if usuario.is_superuser or usuario.has_perm("cuentas.ver_todas_solicitudes"):
        return queryset
    return queryset.filter(Q(solicitante=usuario) | Q(tecnico_asignado=usuario))


def _reparaciones_visibles(usuario):
    queryset = Intervencion.objects.select_related("solicitud__equipo", "solicitud__equipo__categoria", "laboratorio_origen", "tecnico")
    if usuario.is_superuser or usuario.has_perm("cuentas.ver_todas_solicitudes"):
        return queryset
    return queryset.filter(Q(solicitud__solicitante=usuario) | Q(solicitud__tecnico_asignado=usuario))


def _en_periodo(queryset, campo, filtros):
    desde, hasta = _fecha(filtros.get("desde")), _fecha(filtros.get("hasta"))
    if desde:
        queryset = queryset.filter(**{f"{campo}__gte": desde})
    if hasta:
        queryset = queryset.filter(**{f"{campo}__lte": hasta})
    return queryset


def _equipos_por_laboratorio(filtros):
    equipos = _filtrar_equipo(Equipo.objects.select_related("ambiente", "estado"), filtros)
    estados = list(EstadoEquipo.objects.order_by("orden", "pk"))
    headers = ["Laboratorio", *[estado.nombre for estado in estados], "Total"]
    conteo = {}
    for equipo in equipos:
        fila = conteo.setdefault(_laboratorio(equipo.ambiente), {estado.nombre: 0 for estado in estados})
        fila[equipo.estado.nombre] += 1
    filas = []
    for laboratorio, valores in sorted(conteo.items()):
        filas.append({"Laboratorio": laboratorio, **valores, "Total": sum(valores.values())})
    if filas:
        total = {"Laboratorio": "TOTAL", **{estado.nombre: sum(f[estado.nombre] for f in filas) for estado in estados}}
        total["Total"] = sum(f["Total"] for f in filas)
        filas.append(total)
    return headers, filas


def _equipos_reparacion_obsoletos(filtros):
    equipos = _filtrar_equipo(
        Equipo.objects.filter(estado__tipo__in=[EstadoEquipo.Tipo.REPARACION, EstadoEquipo.Tipo.BAJA]).select_related("categoria", "ambiente", "estado", "equipo_principal"),
        filtros,
    ).order_by("estado__orden", "codigo")
    headers = ["Código", "Número de serie", "Equipo", "Laboratorio", "Estado", "Fecha de retiro", "Informado a Vicerrectoría"]
    filas = []
    for e in equipos:
        informado = ""
        if e.esta_de_baja:
            informado = f"Sí ({_fmt(e.fecha_informe_vicerrectoria)})" if e.informado_vicerrectoria else "No"
        nombre = f"{e.categoria} {e.marca} {e.modelo}".strip()
        if e.equipo_principal_id:
            nombre += f" (de {e.equipo_principal.codigo})"
        filas.append({"Código": e.codigo, "Número de serie": e.numero_serie or "—", "Equipo": nombre, "Laboratorio": _laboratorio(e.ambiente), "Estado": e.estado.nombre, "Fecha de retiro": _fmt(e.fecha_baja), "Informado a Vicerrectoría": informado})
    return headers, filas


def _solicitudes(usuario, filtros):
    solicitudes = _en_periodo(_filtrar_equipo(_solicitudes_visibles(usuario), filtros, "equipo__"), "fecha_reporte__date", filtros)
    situacion = filtros.get("situacion", "")
    abiertos = [Solicitud.Estado.REGISTRADA, Solicitud.Estado.ASIGNADA, Solicitud.Estado.EN_REPARACION]
    if situacion == "pendientes":
        solicitudes = solicitudes.filter(estado__in=abiertos)
    elif situacion == "atendidos":
        solicitudes = solicitudes.filter(estado=Solicitud.Estado.RESUELTA)
    headers = ["N.º", "Fecha", "Equipo", "Laboratorio", "Docente solicitante", "Problema", "Estado", "Técnico", "Cierre"]
    filas = [{
        "N.º": s.pk, "Fecha": s.fecha_reporte.strftime("%d/%m/%Y"), "Equipo": s.equipo.codigo, "Laboratorio": _laboratorio(s.equipo.ambiente),
        "Docente solicitante": s.docente_solicitante, "Problema": s.descripcion, "Estado": s.get_estado_display(),
        "Técnico": str(s.tecnico_asignado or "Sin asignar"), "Cierre": s.fecha_cierre.strftime("%d/%m/%Y") if s.fecha_cierre else "",
    } for s in solicitudes.order_by("-fecha_reporte")]
    return headers, filas


def _historial_equipo(usuario, filtros):
    headers = ["Fecha", "Evento", "Detalle", "Usuario"]
    equipo = Equipo.objects.filter(pk=_id(filtros.get("equipo"))).first() if _id(filtros.get("equipo")) else None
    if equipo is None:
        return headers, [], "Elige un equipo para ver su historial completo."
    eventos = []
    for cambio in equipo.historial.select_related("usuario"):
        eventos.append((timezone.localtime(cambio.fecha), "Cambio de " + cambio.get_campo_cambiado_display().lower(), f"{cambio.valor_anterior} → {cambio.valor_nuevo}", str(cambio.usuario or "Sistema")))
    for s in _solicitudes_visibles(usuario).filter(equipo=equipo):
        eventos.append((timezone.localtime(s.fecha_reporte), f"Reporte de falla #{s.pk}", f"{s.descripcion} (docente: {s.docente_solicitante}) · {s.get_estado_display()}", str(s.solicitante)))
    for r in _reparaciones_visibles(usuario).filter(solicitud__equipo=equipo):
        detalle = f"Salida de {_laboratorio(r.laboratorio_origen)}. Diagnóstico: {r.diagnostico}"
        eventos.append((r.fecha_salida, f"Salida a reparación (reporte #{r.solicitud_id})", detalle, str(r.tecnico)))
        if r.fecha_devolucion:
            detalle = f"{r.get_resultado_display()}. {r.trabajo_realizado}".strip()
            if r.repuestos_usados:
                detalle += f" Repuestos: {r.repuestos_usados}"
            eventos.append((r.fecha_devolucion, f"Devolución ({r.dias_fuera} días fuera)", detalle, str(r.tecnico)))
    def _clave(evento):
        fecha = evento[0]
        return fecha.date() if hasattr(fecha, "date") and callable(fecha.date) else fecha
    eventos.sort(key=_clave, reverse=True)
    filas = [{"Fecha": f.strftime("%d/%m/%Y"), "Evento": ev, "Detalle": det, "Usuario": u} for f, ev, det, u in eventos]
    return headers, filas, f"{equipo.codigo} · {equipo.categoria} {equipo.marca} {equipo.modelo}".strip()


def _tiempo_fuera(usuario, filtros):
    reparaciones = _en_periodo(_filtrar_equipo(_reparaciones_visibles(usuario), filtros, "solicitud__equipo__"), "fecha_salida", filtros)
    headers = ["Equipo", "Laboratorio de origen", "Reporte", "Técnico", "Fecha de salida", "Fecha de devolución", "Días fuera"]
    filas = []
    for r in reparaciones.order_by("-fecha_salida"):
        filas.append({
            "Equipo": r.solicitud.equipo.codigo, "Laboratorio de origen": _laboratorio(r.laboratorio_origen), "Reporte": r.solicitud_id,
            "Técnico": str(r.tecnico), "Fecha de salida": _fmt(r.fecha_salida),
            "Fecha de devolución": _fmt(r.fecha_devolucion) or "Sigue fuera",
            "Días fuera": r.dias_fuera if r.terminada else f"{r.dias_fuera} (en curso)",
        })
    terminadas = [r.dias_fuera for r in reparaciones if r.terminada]
    if terminadas:
        filas.append({"Equipo": "PROMEDIO (devueltos)", "Laboratorio de origen": "", "Reporte": "", "Técnico": "", "Fecha de salida": "", "Fecha de devolución": "", "Días fuera": round(sum(terminadas) / len(terminadas), 1)})
    return headers, filas


def _equipos_mas_fallas(usuario, filtros):
    solicitudes = _en_periodo(_filtrar_equipo(_solicitudes_visibles(usuario), filtros, "equipo__"), "fecha_reporte__date", filtros)
    conteos = solicitudes.values("equipo_id").annotate(total=Count("pk")).filter(total__gt=0).order_by("-total")[:50]
    equipos = Equipo.objects.select_related("ambiente", "categoria").in_bulk([c["equipo_id"] for c in conteos])
    headers = ["Código", "Equipo", "Laboratorio", "Número de fallas"]
    filas = []
    for conteo in conteos:
        e = equipos[conteo["equipo_id"]]
        filas.append({"Código": e.codigo, "Equipo": f"{e.categoria} {e.marca} {e.modelo}".strip(), "Laboratorio": _laboratorio(e.ambiente), "Número de fallas": conteo["total"]})
    filas.sort(key=lambda fila: (-fila["Número de fallas"], fila["Código"]))
    return headers, filas


def _mantenimientos_periodo(usuario, filtros):
    headers = ["Fecha", "Tipo", "Laboratorio", "Equipo", "Detalle", "Técnico", "Estado"]
    filas = []
    preventivos = _en_periodo(MantenimientoPreventivo.objects.select_related("laboratorio", "tecnico"), "fecha_programada", filtros)
    if _id(filtros.get("ambiente")):
        preventivos = preventivos.filter(laboratorio_id=_id(filtros["ambiente"]))
    if not (usuario.is_superuser or usuario.has_perm("cuentas.crear_preventivos")):
        preventivos = preventivos.filter(tecnico=usuario)
    for m in preventivos:
        estado = f"Realizado el {_fmt(m.fecha_realizada)}" if m.estado == MantenimientoPreventivo.Estado.REALIZADO else ("Vencido" if m.vencido else "Pendiente")
        filas.append({"_orden": m.fecha_programada, "Fecha": _fmt(m.fecha_programada), "Tipo": "Preventivo", "Laboratorio": m.laboratorio.nombre, "Equipo": "Todo el laboratorio", "Detalle": f"{m.get_numero_display()} {m.anio}", "Técnico": str(m.tecnico or "Sin asignar"), "Estado": estado})
    reparaciones = _en_periodo(_filtrar_equipo(_reparaciones_visibles(usuario), filtros, "solicitud__equipo__"), "fecha_salida", filtros)
    for r in reparaciones:
        estado = f"Devuelto el {_fmt(r.fecha_devolucion)} · {r.get_resultado_display()}" if r.terminada else "En reparación"
        filas.append({"_orden": r.fecha_salida, "Fecha": _fmt(r.fecha_salida), "Tipo": "Correctivo (reparación)", "Laboratorio": _laboratorio(r.laboratorio_origen), "Equipo": r.solicitud.equipo.codigo, "Detalle": r.diagnostico, "Técnico": str(r.tecnico), "Estado": estado})
    filas.sort(key=lambda fila: fila["_orden"], reverse=True)
    for fila in filas:
        fila.pop("_orden")
    return headers, filas


def generar_reporte(clave, usuario, filtros):
    nombre = dict(DEFINICIONES_REPORTES).get(clave)
    if not nombre:
        clave, nombre = DEFINICIONES_REPORTES[0]
    subtitulo = ""
    if clave == "equipos_por_ambiente":
        headers, filas = _equipos_por_laboratorio(filtros)
    elif clave == "equipos_reparacion_obsoletos":
        headers, filas = _equipos_reparacion_obsoletos(filtros)
    elif clave == "solicitudes":
        headers, filas = _solicitudes(usuario, filtros)
    elif clave == "historial_equipo":
        headers, filas, subtitulo = _historial_equipo(usuario, filtros)
    elif clave == "tiempo_fuera":
        headers, filas = _tiempo_fuera(usuario, filtros)
    elif clave == "equipos_mas_fallas":
        headers, filas = _equipos_mas_fallas(usuario, filtros)
    else:
        headers, filas = _mantenimientos_periodo(usuario, filtros)
    return {"clave": clave, "nombre": nombre, "subtitulo": subtitulo, "headers": headers, "filas": filas}
