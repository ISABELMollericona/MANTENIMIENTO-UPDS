import json
from datetime import datetime
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.equipos.models import Equipo
from apps.intervenciones.forms import IntervencionForm
from apps.intervenciones.models import Intervencion, RepuestoUsado
from apps.preventivo.models import MantenimientoProgramado
from apps.preventivo.services import completar_mantenimiento
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
        equipos = Equipo.objects.filter(estado__in=[Equipo.Estado.OPERATIVO, Equipo.Estado.EN_MANTENIMIENTO, Equipo.Estado.FUERA_DE_SERVICIO]).select_related("categoria", "ambiente")
        payload["equipos"] = [{
            "id": item.pk,
            "codigo": item.codigo,
            "marca": item.marca,
            "modelo": item.modelo,
            "ambiente": item.ambiente.nombre if item.ambiente else None,
            "estado": item.estado,
        } for item in equipos]

    if request.user.has_perm("cuentas.ver_ambientes"):
        ambientes = Ambiente.objects.filter(activo=True).order_by("bloque", "nombre")
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
            "estado": item.estado,
            "prioridad": item.prioridad,
            "fecha_reporte": item.fecha_reporte.isoformat(),
        } for item in queryset.order_by("-fecha_reporte")[:50]]
        payload["solicitudes"] = tareas
        payload["solicitudes_asignadas"] = tareas
        payload["mis_tareas"] = tareas

    if request.user.has_perm("cuentas.ver_preventivos"):
        pendientes = MantenimientoProgramado.objects.filter(estado=MantenimientoProgramado.Estado.PENDIENTE).select_related("equipo", "equipo__ambiente", "plan")
        payload["preventivos_pendientes"] = [{
            "id": item.pk,
            "equipo": item.equipo.codigo,
            "plan": item.plan.nombre,
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
            return JsonResponse({"estado": "duplicado", "id": existente.pk, "mensaje": "La solicitud ya estaba sincronizada."}, status=200)
        try:
            form_data = {
                "equipo": datos.get("equipo"),
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
                solicitud.tecnico_asignado_id = datos.get("tecnico_asignado")
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
            return JsonResponse({"estado": "ok", "id": solicitud.pk, "mensaje": "Solicitud sincronizada correctamente."}, status=200)
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
        if solicitud.estado not in {Solicitud.Estado.ASIGNADA, Solicitud.Estado.EN_REPARACION}:
            return _json_error("La solicitud no está disponible para registrar la intervención.")
        if solicitud.tecnico_asignado_id != request.user.pk:
            return _json_error("Solo el técnico asignado puede registrar esta intervención.")
        try:
            form_data = {
                "diagnostico": datos.get("diagnostico", ""),
                "trabajo_realizado": datos.get("trabajo_realizado", ""),
                "fecha_inicio": datos.get("fecha_inicio") or timezone.now().isoformat(),
                "fecha_fin": datos.get("fecha_fin") or "",
                "costo_mano_obra": datos.get("costo_mano_obra", "0.00"),
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
                intervencion.full_clean()
                intervencion.save()
                for repuesto in datos.get("repuestos", []):
                    RepuestoUsado.objects.create(
                        intervencion=intervencion,
                        descripcion=str(repuesto.get("descripcion", "")).strip(),
                        cantidad=repuesto.get("cantidad", "0.01"),
                        costo_unitario=repuesto.get("costo_unitario", "0.00"),
                    )
                if solicitud.estado == Solicitud.Estado.ASIGNADA:
                    solicitud = cambiar_estado(solicitud, Solicitud.Estado.EN_REPARACION, request.user, "Intervención iniciada desde modo sin conexión.")
                if intervencion.fecha_fin:
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
        if programacion_id:
            programacion = MantenimientoProgramado.objects.filter(pk=programacion_id).select_for_update().first()
        else:
            programacion = MantenimientoProgramado.objects.filter(
                equipo_id=datos.get("equipo"),
                plan_id=datos.get("plan"),
                fecha_programada=datos.get("fecha_programada"),
            ).select_for_update().first()
        if not programacion:
            return _json_error("La programación preventiva no existe o ya no está pendiente.")
        if programacion.estado == MantenimientoProgramado.Estado.REALIZADO:
            return JsonResponse({"estado": "duplicado", "id": programacion.pk, "mensaje": "El mantenimiento preventivo ya estaba registrado como realizado."}, status=200)
        try:
            with transaction.atomic():
                _, siguiente = completar_mantenimiento(programacion, request.user)
            return JsonResponse({"estado": "ok", "id": programacion.pk, "mensaje": "Mantenimiento preventivo sincronizado correctamente."}, status=200)
        except ValidationError as exc:
            return _json_error(exc.messages[0] if getattr(exc, "messages", None) else str(exc))

    return _json_error("Tipo de operación no soportado.")
