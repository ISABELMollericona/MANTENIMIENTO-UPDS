from django.db import migrations
from django.utils import timezone


def _fecha_local(valor):
    if valor is None:
        return None
    return timezone.localtime(valor).date() if timezone.is_aware(valor) else valor.date()


def migrar(apps, schema_editor):
    Intervencion = apps.get_model("intervenciones", "Intervencion")
    RepuestoUsado = apps.get_model("intervenciones", "RepuestoUsado")
    for intervencion in Intervencion.objects.select_related("solicitud__equipo"):
        intervencion.fecha_salida = _fecha_local(intervencion.fecha_inicio) or timezone.localdate()
        intervencion.fecha_devolucion = _fecha_local(intervencion.fecha_fin)
        intervencion.laboratorio_origen_id = intervencion.solicitud.equipo.ambiente_id
        # Los repuestos pasan a texto, sin costos (fuera del alcance acordado).
        lineas = []
        for repuesto in RepuestoUsado.objects.filter(intervencion=intervencion).order_by("pk"):
            cantidad = repuesto.cantidad.normalize() if repuesto.cantidad is not None else ""
            lineas.append(f"{repuesto.descripcion} x {cantidad}".strip())
        intervencion.repuestos_usados = "\n".join(lineas)
        intervencion.save(update_fields=["fecha_salida", "fecha_devolucion", "laboratorio_origen", "repuestos_usados"])


class Migration(migrations.Migration):
    dependencies = [("intervenciones", "0003_reparacion_campos")]
    operations = [migrations.RunPython(migrar, migrations.RunPython.noop)]
