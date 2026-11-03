from django.contrib import admin

from .models import MantenimientoProgramado, PlanPreventivo


@admin.register(PlanPreventivo)
class PlanPreventivoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "periodicidad_meses", "activo")
    list_filter = ("categoria", "activo")
    search_fields = ("nombre", "actividades")


@admin.register(MantenimientoProgramado)
class MantenimientoProgramadoAdmin(admin.ModelAdmin):
    list_display = ("equipo", "plan", "fecha_programada", "tecnico", "estado")
    list_filter = ("estado", "fecha_programada", "plan__categoria")
    search_fields = ("equipo__codigo", "plan__nombre")