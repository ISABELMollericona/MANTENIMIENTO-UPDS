import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("intervenciones", "0004_migrar_datos_reparacion")]

    operations = [
        migrations.RemoveIndex(model_name="intervencion", name="int_tecnico_inicio_idx"),
        migrations.RemoveField(model_name="intervencion", name="costo_mano_obra"),
        migrations.RemoveField(model_name="intervencion", name="fecha_inicio"),
        migrations.RemoveField(model_name="intervencion", name="fecha_fin"),
        migrations.DeleteModel(name="RepuestoUsado"),
        migrations.AlterField(
            model_name="intervencion",
            name="fecha_salida",
            field=models.DateField(db_index=True, default=django.utils.timezone.localdate, verbose_name="Fecha de salida"),
        ),
        migrations.AlterModelOptions(
            name="intervencion",
            options={"ordering": ["fecha_salida", "pk"], "verbose_name": "reparación", "verbose_name_plural": "reparaciones"},
        ),
        migrations.AddIndex(model_name="intervencion", index=models.Index(fields=["tecnico", "fecha_salida"], name="rep_tecnico_salida_idx")),
    ]
