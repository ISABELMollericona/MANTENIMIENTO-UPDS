import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("solicitudes", "0003_solicitud_offline_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="solicitud",
            options={"ordering": ["-fecha_reporte", "-pk"], "verbose_name": "reporte de falla", "verbose_name_plural": "reportes de falla"},
        ),
        # Los reportes anteriores no tenían este dato: quedan como "No registrado".
        migrations.AddField(
            model_name="solicitud",
            name="docente_solicitante",
            field=models.CharField(default="No registrado", max_length=150, verbose_name="Docente solicitante"),
            preserve_default=False,
        ),
        migrations.AlterField(model_name="solicitud", name="descripcion", field=models.TextField(verbose_name="Problema que presenta el equipo")),
        migrations.AlterField(
            model_name="solicitud",
            name="solicitante",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="solicitudes_reportadas", to=settings.AUTH_USER_MODEL, verbose_name="Registrado por"),
        ),
    ]
