from django.contrib import admin

from .models import Ambiente


@admin.register(Ambiente)
class AmbienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "bloque", "responsable", "activo")
    list_filter = ("tipo", "bloque", "activo")
    search_fields = ("nombre", "bloque", "responsable__username")