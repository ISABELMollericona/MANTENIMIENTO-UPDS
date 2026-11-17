import django.db.models.deletion
from django.db import migrations, models

ESTADOS_INICIALES = [
    # (nombre visible, tipo, orden) — los nombres se pueden editar desde el sistema.
    ("Operativo", "operativo", 1),
    ("En mantenimiento/reparación", "reparacion", 2),
    ("Obsoleto/Dado de baja", "baja", 3),
]


def crear_estados(apps, schema_editor):
    EstadoEquipo = apps.get_model("equipos", "EstadoEquipo")
    for nombre, tipo, orden in ESTADOS_INICIALES:
        EstadoEquipo.objects.get_or_create(nombre=nombre, defaults={"tipo": tipo, "orden": orden})


class Migration(migrations.Migration):
    dependencies = [("equipos", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="EstadoEquipo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=80, unique=True, verbose_name="Nombre")),
                ("tipo", models.CharField(choices=[("operativo", "Disponible (operativo)"), ("reparacion", "Fuera por mantenimiento o reparación"), ("baja", "Retirado (obsoleto o dado de baja)")], db_index=True, max_length=12, verbose_name="Comportamiento en el sistema")),
                ("orden", models.PositiveSmallIntegerField(default=0, verbose_name="Orden")),
                ("activo", models.BooleanField(db_index=True, default=True, verbose_name="Activo")),
            ],
            options={"verbose_name": "estado de equipo", "verbose_name_plural": "estados de equipo", "ordering": ["orden", "nombre"]},
        ),
        migrations.RunPython(crear_estados, migrations.RunPython.noop),
        migrations.AddField(
            model_name="categoriaequipo",
            name="es_periferico",
            field=models.BooleanField(default=False, help_text="Márcalo para teclados, mouse y otros periféricos que se asocian a una computadora.", verbose_name="Es periférico"),
        ),
        migrations.AddField(
            model_name="equipo",
            name="equipo_principal",
            field=models.ForeignKey(blank=True, help_text="Solo para periféricos (teclado, mouse): la computadora a la que pertenecen.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="perifericos", to="equipos.equipo", verbose_name="Computadora asociada"),
        ),
        migrations.AddField(model_name="equipo", name="fecha_baja", field=models.DateField(blank=True, null=True, verbose_name="Fecha de retiro")),
        migrations.AddField(model_name="equipo", name="motivo_baja", field=models.TextField(blank=True, verbose_name="Motivo del retiro")),
        migrations.AddField(model_name="equipo", name="informado_vicerrectoria", field=models.BooleanField(default=False, verbose_name="Informado a Vicerrectoría Administrativa")),
        migrations.AddField(model_name="equipo", name="fecha_informe_vicerrectoria", field=models.DateField(blank=True, null=True, verbose_name="Fecha en que se informó a Vicerrectoría")),
        migrations.RemoveIndex(model_name="equipo", name="eq_estado_cat_idx"),
        migrations.RemoveIndex(model_name="equipo", name="eq_amb_estado_idx"),
        migrations.AddField(
            model_name="equipo",
            name="estado_ref",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="equipos.estadoequipo"),
        ),
    ]
