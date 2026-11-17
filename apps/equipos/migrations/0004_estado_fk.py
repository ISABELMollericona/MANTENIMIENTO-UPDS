import django.db.models.deletion
from django.db import migrations, models

import apps.equipos.models


class Migration(migrations.Migration):
    dependencies = [("equipos", "0003_migrar_estados")]

    operations = [
        migrations.RemoveField(model_name="equipo", name="estado"),
        migrations.RenameField(model_name="equipo", old_name="estado_ref", new_name="estado"),
        migrations.AlterField(
            model_name="equipo",
            name="estado",
            field=models.ForeignKey(default=apps.equipos.models.estado_operativo_por_defecto, on_delete=django.db.models.deletion.PROTECT, related_name="equipos", to="equipos.estadoequipo", verbose_name="Estado"),
        ),
        migrations.AddIndex(model_name="equipo", index=models.Index(fields=["estado", "categoria"], name="eq_estado_cat_idx")),
        migrations.AddIndex(model_name="equipo", index=models.Index(fields=["ambiente", "estado"], name="eq_amb_estado_idx")),
        # Los costos están fuera del alcance acordado con el cliente.
        migrations.RemoveField(model_name="equipo", name="costo_compra"),
    ]
