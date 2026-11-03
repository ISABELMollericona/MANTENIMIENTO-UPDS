from django.contrib import admin

from .models import HistorialSolicitud, Solicitud


class HistorialSolicitudInline(admin.TabularInline):
    model = HistorialSolicitud
    extra = 0
    can_delete = False
    readonly_fields = ("estado_anterior", "estado_nuevo", "usuario", "fecha", "comentario")


@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = ("id", "equipo", "prioridad", "estado", "solicitante", "tecnico_asignado", "fecha_reporte")
    list_filter = ("estado", "prioridad", "fecha_reporte", "equipo__ambiente")
    search_fields = ("equipo__codigo", "descripcion", "solicitante__username")
    inlines = [HistorialSolicitudInline]