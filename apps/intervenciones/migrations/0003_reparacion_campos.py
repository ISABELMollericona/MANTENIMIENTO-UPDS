import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("intervenciones", "0002_intervencion_offline_fields"),
        ("ubicaciones", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="intervencion",
            name="laboratorio_origen",
            field=models.ForeignKey(blank=True, help_text="Laboratorio del que salió el equipo (se guarda aunque luego cambie de laboratorio).", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reparaciones", to="ubicaciones.ambiente", verbose_name="Laboratorio de origen"),
        ),
        migrations.AddField(model_name="intervencion", name="fecha_salida", field=models.DateField(null=True, verbose_name="Fecha de salida")),
        migrations.AddField(model_name="intervencion", name="fecha_devolucion", field=models.DateField(blank=True, db_index=True, null=True, verbose_name="Fecha de devolución")),
        migrations.AddField(model_name="intervencion", name="repuestos_usados", field=models.TextField(blank=True, help_text="Escribe los repuestos que se cambiaron, uno por línea.", verbose_name="Repuestos usados")),
    ]
