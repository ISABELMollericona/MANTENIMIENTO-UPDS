from django.db import migrations

# Estados anteriores (texto fijo en el código) -> tipo del nuevo estado editable.
# "Fuera de servicio" no es un estado del cliente: el equipo sigue sin poder usarse,
# por eso pasa a "En mantenimiento/reparación" hasta que el responsable decida.
MAPA = {
    "operativo": "operativo",
    "en_mantenimiento": "reparacion",
    "fuera_de_servicio": "reparacion",
    "dado_de_baja": "baja",
}


def migrar(apps, schema_editor):
    Equipo = apps.get_model("equipos", "Equipo")
    EstadoEquipo = apps.get_model("equipos", "EstadoEquipo")
    por_tipo = {e.tipo: e for e in reversed(list(EstadoEquipo.objects.order_by("orden", "pk")))}
    for equipo in Equipo.objects.all():
        tipo = MAPA.get(equipo.estado, "operativo")
        equipo.estado_ref = por_tipo[tipo]
        if tipo == "baja" and not equipo.fecha_baja:
            equipo.fecha_baja = equipo.actualizado_en.date()
        equipo.save(update_fields=["estado_ref", "fecha_baja"])


def revertir(apps, schema_editor):
    Equipo = apps.get_model("equipos", "Equipo")
    inverso = {"operativo": "operativo", "reparacion": "en_mantenimiento", "baja": "dado_de_baja"}
    for equipo in Equipo.objects.select_related("estado_ref"):
        equipo.estado = inverso[equipo.estado_ref.tipo] if equipo.estado_ref_id else "operativo"
        equipo.save(update_fields=["estado"])


class Migration(migrations.Migration):
    dependencies = [("equipos", "0002_estados_editables")]
    operations = [migrations.RunPython(migrar, revertir)]
