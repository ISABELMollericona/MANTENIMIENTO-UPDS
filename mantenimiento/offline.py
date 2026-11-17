import json
from datetime import datetime
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.equipos.models import Equipo, EstadoEquipo
from apps.intervenciones.forms import IntervencionForm
from apps.intervenciones.models import Intervencion
from apps.preventivo.models import MantenimientoPreventivo
from apps.solicitudes.forms import SolicitudForm
from apps.solicitudes.models import HistorialSolicitud, Solicitud
from apps.solicitudes.services import cambiar_estado
from apps.ubicaciones.models import Ambiente


def _parse_fecha_cliente(value, fallback=None):
    if value in (None, "", "null"):
        return fallback or timezone.now()
    if isinstance(value, datetime):
        fecha = value
    else:
        try:
            fecha = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            fecha = timezone.now()
    if timezone.is_aware(fecha):
        return fecha
    return timezone.make_aware(fecha, timezone.get_current_timezone())


def _json_error(mensaje, status=400, **extra):
    payload = {"estado": "error", "id": None, "mensaje": mensaje}
    payload.update(extra)
    return JsonResponse(payload, status=status)


@login_required
@require_http_methods(["GET"])
def catalogos_offline(request):
    payload = {
        "generada_en": timezone.now().isoformat(),
        "equipos": [],
        "ambientes": [],
        "solicitudes": [],
        "solicitudes_asignadas": [],
        "mis_tareas": [],
        "preventivos_pendientes": [],
    }

    if request.user.has_perm("cuentas.ver_equipos"):
        equipos = Equipo.objects.exclude(estado__tipo=EstadoEquipo.Tipo.BAJA).select_related("categoria", "ambiente", "estado")
        payload["equipos"] = [{
            "id": item.pk,
            "codigo": item.codigo,
            "marca": item.marca,
            "modelo": item.modelo,
            "ambiente": item.ambiente.nombre if item.ambiente else None,
            "estado": item.estado.nombre,
        } for item in equipos]

    if request.user.has_perm("cuentas.ver_ambientes"):
        ambientes = Ambiente.laboratorios()
        payload["ambientes"] = [{
            "id": item.pk,
            "nombre": item.nombre,
            "bloque": item.bloque,
            "tipo": item.tipo,
        } for item in ambientes]

    if request.user.has_perm("cuentas.ver_solicitudes"):
        queryset = Solicitud.objects.filter(tecnico_asignado=request.user).select_related("equipo", "equipo__ambiente", "solicitante")
        tareas = [{
            "id": item.pk,
            "equipo": item.equipo.codigo,
            "descripcion": item.descripcion,
            "docente_solicitante": item.docente_solicitante,
            "estado": item.estado,
            "prioridad": item.prioridad,
            "fecha_reporte": item.fecha_reporte.isoformat(),
        } for item in queryset.order_by("-fecha_reporte")[:50]]
        payload["solicitudes"] = tareas
        payload["solicitudes_asignadas"] = tareas
        payload["mis_tareas"] = tareas

    if request.user.has_perm("cuentas.ver_preventivos"):
        pendientes = MantenimientoPreventivo.objects.filter(estado=MantenimientoPreventivo.Estado.PENDIENTE).select_related("laboratorio")
        if not (request.user.is_superuser or request.user.has_perm("cuentas.crear_preventivos")):
            pendientes = pendientes.filter(tecnico=request.user)
        payload["preventivos_pendientes"] = [{
            "id": item.pk,
            "laboratorio": item.laboratorio.nombre,
            "mantenimiento": item.get_numero_display(),
            "fecha_programada": item.fecha_programada.isoformat(),
            "estado": item.estado,
        } for item in pendientes.order_by("fecha_programada")]

    return JsonResponse(payload)


@login_required
@require_http_methods(["POST"])
def sincronizar_offline(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}") if request.body else request.POST
    except json.JSONDecodeError:
        return _json_error("La operación enviada no tiene un formato válido.")

    tipo = str(payload.get("tipo", "")).strip()
    uuid_cliente = payload.get("uuid_cliente")
    fecha_cliente = payload.get("fecha_cliente")
    datos = payload.get("datos") if isinstance(payload.get("datos"), dict) else {}
    if not tipo:
        return _json_error("Falta el tipo de operación.")
    if not uuid_cliente:
        return _json_error("Falta el identificador del registro." )

    try:
        uuid_obj = UUID(str(uuid_cliente))
    except (TypeError, ValueError):
        return _json_error("El UUID del cliente no es válido.")

    if tipo == "solicitud":
        if not request.user.has_perm("cuentas.crear_solicitudes"):
            return _json_error("No tienes permisos para registrar solicitudes desde modo sin conexión.")
        existente = Solicitud.objects.filter(uuid_cliente=uuid_obj).first()
        if existente:
            return JsonResponse({"estado": "duplicado", "id": existente.pk, "mensaje": "El reporte de falla ya estaba sincronizado."}, status=200)
        try:
            form_data = {
                "equipo": datos.get("equipo"),
                "docente_solicitante": datos.get("docente_solicitante", ""),
                "descripcion": datos.get("descripcion", ""),
                "prioridad": datos.get("prioridad", Solicitud.Prioridad.MEDIA),
            }
            formulario = SolicitudForm(data=form_data)
            if not formulario.is_valid():
                mensaje = "; ".join(value[0] for value in formulario.errors.values())
                raise ValidationError(mensaje)
            fecha_registro = _parse_fecha_cliente(fecha_cliente, timezone.now())
            with transaction.atomic():
                solicitud = formulario.save(commit=False)
                solicitud.solicitante = request.user
                solicitud.creado_por = request.user
                solicitud.uuid_cliente = uuid_obj
                solicitud.creado_sin_conexion = True
                solicitud.fecha_cliente = fecha_registro
                solicitud.fecha_reporte = fecha_registro
                solicitud.full_clean()
                solicitud.save()
                HistorialSolicitud.objects.create(
                    solicitud=solicitud,
                    estado_anterior=solicitud.estado,
                    estado_nuevo=solicitud.estado,
                    usuario=request.user,
                    comentario="Registro sincronizado desde modo sin conexión.",
                )
            return JsonResponse({"estado": "ok", "id": solicitud.pk, "mensaje": "Reporte de falla sincronizado correctamente."}, status=200)
        except ValidationError as exc:
            mensaje = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            return _json_error(mensaje)

    if tipo == "intervencion":
        if not request.user.has_perm("cuentas.crear_intervenciones"):
            return _json_error("No tienes permisos para registrar intervenciones desde modo sin conexión.")
        existente = Intervencion.objects.filter(uuid_cliente=uuid_obj).first()
        if existente:
            return JsonResponse({"estado": "duplicado", "id": existente.pk, "mensaje": "La intervención ya estaba sincronizada."}, status=200)
        solicitud_id = datos.get("solicitud")
        if not solicitud_id:
            return _json_error("Falta la solicitud asociada a la intervención.")
        try:
            solicitud = Solicitud.objects.select_for_update().get(pk=solicitud_id)
        except Solicitud.DoesNotExist:
            return _json_error("La solicitud indicada no existe.")
        if solicitud.estado != Solicitud.Estado.ASIGNADA:
            return _json_error("El reporte no está disponible para registrar la reparación.")
        if solicitud.tecnico_asignado_id != request.user.pk:
            return _json_error("Solo el técnico asignado puede registrar esta intervención.")
        try:
            form_data = {
                "diagnostico": datos.get("diagnostico", ""),
                "trabajo_realizado": datos.get("trabajo_realizado", ""),
                "fecha_salida": datos.get("fecha_salida") or timezone.localdate().isoformat(),
                "fecha_devolucion": datos.get("fecha_devolucion") or "",
                "repuestos_usados": datos.get("repuestos_usados", ""),
                "resultado": datos.get("resultado", ""),
                "observaciones": datos.get("observaciones", ""),
            }
            formulario = IntervencionForm(data=form_data)
            if not formulario.is_valid():
                mensaje = "; ".join(value[0] for value in formulario.errors.values())
                raise ValidationError(mensaje)
            fecha_registro = _parse_fecha_cliente(fecha_cliente, timezone.now())
            with transaction.atomic():
                intervencion = formulario.save(commit=False)
                intervencion.solicitud = solicitud
                intervencion.tecnico = request.user
                intervencion.creado_por = request.user
                intervencion.uuid_cliente = uuid_obj
                intervencion.creado_sin_conexion = True
                intervencion.fecha_cliente = fecha_registro
                intervencion.laboratorio_origen = solicitud.equipo.ambiente
                intervencion.full_clean()
                intervencion.save()
                if solicitud.estado == Solicitud.Estado.ASIGNADA:
                    solicitud = cambiar_estado(solicitud, Solicitud.Estado.EN_REPARACION, request.user, "Intervención iniciada desde modo sin conexión.")
                if intervencion.fecha_devolucion:
                    solicitud = cambiar_estado(
                        solicitud,
                        Solicitud.Estado.RESUELTA,
                        request.user,
                        comentario=f"Intervención finalizada desde modo sin conexión: {intervencion.get_resultado_display()}.",
                        no_reparable=intervencion.resultado == Intervencion.Resultado.NO_REPARABLE,
                    )
            return JsonResponse({"estado": "ok", "id": intervencion.pk, "mensaje": "Intervención sincronizada correctamente."}, status=200)
        except ValidationError as exc:
            mensaje = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            return _json_error(mensaje)

    if tipo == "preventivo_realizado":
        if not request.user.has_perm("cuentas.editar_preventivos"):
            return _json_error("No tienes permisos para marcar preventivos realizados.")
        programacion_id = datos.get("programacion_id") or datos.get("mantenimiento_id")
        with transaction.atomic():
            programacion = MantenimientoPreventivo.objects.filter(pk=programacion_id).select_for_update().first() if programacion_id else None
            if not programacion:
                return _json_error("El mantenimiento preventivo no existe.")
            if not (request.user.is_superuser or request.user.has_perm("cuentas.crear_preventivos")) and programacion.tecnico_id != request.user.pk:
                return _json_error("Solo puedes marcar los mantenimientos que tienes asignados.")
            if programacion.estado == MantenimientoPreventivo.Estado.REALIZADO:
                return JsonResponse({"estado": "duplicado", "id": programacion.pk, "mensaje": "El mantenimiento preventivo ya estaba registrado como realizado."}, status=200)
            fecha = datos.get("fecha_realizada") or timezone.localdate().isoformat()
            try:
                programacion.fecha_realizada = datetime.fromisoformat(str(fecha)).date()
            except ValueError:
                return _json_error("La fecha de realización no es válida.")
            programacion.estado = MantenimientoPreventivo.Estado.REALIZADO
            programacion.observaciones = str(datos.get("observaciones", programacion.observaciones))
            programacion.actualizado_por = request.user
            try:
                programacion.full_clean()
            except ValidationError as exc:
                return _json_error(exc.messages[0])
            programacion.save()
        return JsonResponse({"estado": "ok", "id": programacion.pk, "mensaje": "Mantenimiento preventivo sincronizado correctamente."}, status=200)

    return _json_error("Tipo de operación no soportado.")
