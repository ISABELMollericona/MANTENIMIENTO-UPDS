from django.contrib import admin

from .models import CategoriaEquipo, Equipo, HistorialEquipo


@admin.register(CategoriaEquipo)
class CategoriaEquipoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo", "creado_en")
    list_filter = ("activo",)
    search_fields = ("nombre",)


class HistorialEquipoInline(admin.TabularInline):
    model = HistorialEquipo
    extra = 0
    can_delete = False
    readonly_fields = ("campo_cambiado", "valor_anterior", "valor_nuevo", "usuario", "fecha")


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "categoria", "ambiente", "responsable", "estado")
    list_filter = ("estado", "categoria", "ambiente")
    search_fields = ("codigo", "marca", "modelo", "numero_serie")
    inlines = [HistorialEquipoInline]