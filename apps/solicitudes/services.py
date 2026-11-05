from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.cuentas.models import AuditoriaSeguridad
from apps.equipos.models import Equipo

from .models import HistorialSolicitud, Solicitud

TRANSICIONES_PERMITIDAS = {
    Solicitud.Estado.REGISTRADA: {Solicitud.Estado.ASIGNADA, Solicitud.Estado.CANCELADA},
    Solicitud.Estado.ASIGNADA: {Solicitud.Estado.EN_REPARACION, Solicitud.Estado.CANCELADA},
    Solicitud.Estado.EN_REPARACION: {Solicitud.Estado.RESUELTA, Solicitud.Estado.CANCELADA},
    Solicitud.Estado.RESUELTA: {Solicitud.Estado.REGISTRADA},
    Solicitud.Estado.CANCELADA: {Solicitud.Estado.REGISTRADA},
}


@transaction.atomic
def asignar_tecnico(solicitud, tecnico, usuario):
    if not usuario.has_perm("cuentas.asignar_tecnico"):
        raise PermissionDenied("No tienes permiso para asignar técnicos.")
    actual = Solicitud.objects.select_for_update(of=("self",)).select_related("tecnico_asignado").get(pk=solicitud.pk)
    if actual.estado not in {Solicitud.Estado.REGISTRADA, Solicitud.Estado.ASIGNADA}:
        raise ValidationError("Solo se puede asignar técnico a una solicitud registrada o asignada.")
    if not tecnico.is_active or not tecnico.has_perm("cuentas.crear_intervenciones"):
        raise ValidationError("El usuario seleccionado no tiene permiso para atender intervenciones.")
    tecnico_anterior = actual.tecnico_asignado
    actual.tecnico_asignado = tecnico
    if actual.estado == Solicitud.Estado.REGISTRADA:
        actual.estado = Solicitud.Estado.ASIGNADA
        actual.save(update_fields=["tecnico_asignado", "estado", "actualizado_en"])
        HistorialSolicitud.objects.create(
            solicitud=actual,
            estado_anterior=Solicitud.Estado.REGISTRADA,
            estado_nuevo=Solicitud.Estado.ASIGNADA,
            usuario=usuario,
            comentario=f"Técnico asignado: {tecnico}.",
        )
    else:
        actual.save(update_fields=["tecnico_asignado", "actualizado_en"])
    AuditoriaSeguridad.objects.create(
        usuario=usuario,
        accion="tecnico_asignado",
        detalle=f"Solicitud #{actual.pk}: {tecnico_anterior or 'sin asignar'} -> {tecnico}.",
    )
    return actual


@transaction.atomic
def cambiar_estado(solicitud, nuevo_estado, usuario, comentario="", motivo_cancelacion="", no_reparable=False):
    actual = Solicitud.objects.select_for_update().select_related("equipo").get(pk=solicitud.pk)
    reapertura = nuevo_estado == Solicitud.Estado.REGISTRADA and actual.estado in {Solicitud.Estado.RESUELTA, Solicitud.Estado.CANCELADA}
    cancelacion_propia = nuevo_estado == Solicitud.Estado.CANCELADA and actual.solicitante_id == usuario.pk and usuario.has_perm("cuentas.cancelar_solicitudes")
    permiso_requerido = "cuentas.reabrir_solicitud" if reapertura else "cuentas.cambiar_estado_solicitud"
    if not usuario.has_perm(permiso_requerido) and not cancelacion_propia:
        raise PermissionDenied("No tienes permiso para realizar este cambio de estado.")
    if nuevo_estado not in dict(Solicitud.Estado.choices):
        raise ValidationError("El estado solicitado no es válido.")
    if nuevo_estado not in TRANSICIONES_PERMITIDAS[actual.estado]:
        raise ValidationError(f"No se puede cambiar de {actual.get_estado_display()} a {dict(Solicitud.Estado.choices)[nuevo_estado]}.")
    if nuevo_estado == Solicitud.Estado.CANCELADA and not motivo_cancelacion.strip():
        raise ValidationError("Indica el motivo de cancelación.")

    anterior = actual.estado
    actual.estado = nuevo_estado
    if nuevo_estado == Solicitud.Estado.CANCELADA:
        actual.motivo_cancelacion = motivo_cancelacion.strip()
        actual.fecha_cierre = timezone.now()
    elif nuevo_estado == Solicitud.Estado.RESUELTA:
        actual.fecha_cierre = timezone.now()
        actual.motivo_cancelacion = ""
    elif nuevo_estado == Solicitud.Estado.REGISTRADA:
        actual.fecha_cierre = None
        actual.motivo_cancelacion = ""
    actual.save(update_fields=["estado", "motivo_cancelacion", "fecha_cierre", "actualizado_en"])
    HistorialSolicitud.objects.create(
        solicitud=actual,
        estado_anterior=anterior,
        estado_nuevo=nuevo_estado,
        usuario=usuario,
        comentario=comentario.strip() or motivo_cancelacion.strip(),
    )

    equipo = actual.equipo
    if equipo.estado != Equipo.Estado.DADO_DE_BAJA:
        if nuevo_estado == Solicitud.Estado.EN_REPARACION:
            equipo.estado = Equipo.Estado.EN_MANTENIMIENTO
        elif anterior == Solicitud.Estado.EN_REPARACION or nuevo_estado == Solicitud.Estado.RESUELTA:
            equipo.estado = Equipo.Estado.FUERA_DE_SERVICIO if no_reparable else Equipo.Estado.OPERATIVO
        equipo._usuario_actualizacion = usuario
        equipo.save(update_fields=["estado", "actualizado_en"])
    return actual