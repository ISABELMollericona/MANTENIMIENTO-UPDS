import calendar
from datetime import date

from django.db import transaction


def agregar_meses(fecha, meses):
    mes_cero = fecha.month - 1 + meses
    anio = fecha.year + mes_cero // 12
    mes = mes_cero % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


@transaction.atomic
def completar_mantenimiento(mantenimiento, usuario):
    from django.utils import timezone

    from .models import MantenimientoProgramado

    actual = MantenimientoProgramado.objects.select_for_update().select_related("plan", "equipo").get(pk=mantenimiento.pk)
    if actual.estado != MantenimientoProgramado.Estado.PENDIENTE:
        return actual, None
    actual.estado = MantenimientoProgramado.Estado.REALIZADO
    actual.fecha_realizada = timezone.localdate()
    actual.actualizado_por = usuario
    actual.save(update_fields=["estado", "fecha_realizada", "actualizado_por", "actualizado_en"])
    siguiente_fecha = agregar_meses(actual.fecha_realizada, actual.plan.periodicidad_meses)
    siguiente, _ = MantenimientoProgramado.objects.get_or_create(
        equipo=actual.equipo,
        plan=actual.plan,
        fecha_programada=siguiente_fecha,
        defaults={"tecnico": actual.tecnico, "creado_por": usuario},
    )
    return actual, siguiente