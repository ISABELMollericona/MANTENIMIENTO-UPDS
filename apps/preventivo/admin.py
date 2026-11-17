from django.contrib import admin

from .models import MantenimientoPreventivo


@admin.register(MantenimientoPreventivo)
class MantenimientoPreventivoAdmin(admin.ModelAdmin):
    list_display = ("laboratorio", "anio", "numero", "fecha_programada", "tecnico", "estado", "fecha_realizada")
    list_filter = ("anio", "estado", "laboratorio")
