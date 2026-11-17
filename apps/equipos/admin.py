from django.contrib import admin

from .models import CategoriaEquipo, Equipo, EstadoEquipo, HistorialEquipo


@admin.register(CategoriaEquipo)
class CategoriaEquipoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "es_periferico", "activo", "creado_en")
    list_filter = ("es_periferico", "activo")
    search_fields = ("nombre",)


@admin.register(EstadoEquipo)
class EstadoEquipoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "orden", "activo")
    list_filter = ("tipo", "activo")


class HistorialEquipoInline(admin.TabularInline):
    model = HistorialEquipo
    extra = 0
    can_delete = False
    readonly_fields = ("campo_cambiado", "valor_anterior", "valor_nuevo", "usuario", "fecha")


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "categoria", "ambiente", "equipo_principal", "estado", "informado_vicerrectoria")
    list_filter = ("estado", "categoria", "ambiente", "informado_vicerrectoria")
    search_fields = ("codigo", "marca", "modelo", "numero_serie")
    inlines = [HistorialEquipoInline]
