from django.contrib import admin

from .models import Intervencion, RepuestoUsado


class RepuestoUsadoInline(admin.TabularInline):
    model = RepuestoUsado
    extra = 0


@admin.register(Intervencion)
class IntervencionAdmin(admin.ModelAdmin):
    list_display = ("id", "solicitud", "tecnico", "fecha_inicio", "fecha_fin", "resultado", "costo_mano_obra")
    list_filter = ("resultado", "fecha_inicio", "tecnico")
    search_fields = ("solicitud__equipo__codigo", "diagnostico", "tecnico__username")
    inlines = [RepuestoUsadoInline]