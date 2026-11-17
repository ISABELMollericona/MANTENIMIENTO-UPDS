from django.contrib import admin

from .models import Intervencion


@admin.register(Intervencion)
class IntervencionAdmin(admin.ModelAdmin):
    list_display = ("id", "solicitud", "tecnico", "laboratorio_origen", "fecha_salida", "fecha_devolucion", "resultado")
    list_filter = ("resultado", "fecha_salida", "tecnico")
    search_fields = ("solicitud__equipo__codigo", "diagnostico", "tecnico__username")
