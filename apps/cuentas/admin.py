from django.contrib import admin
from django.contrib.auth.models import Group

from .models import AuditoriaSeguridad

try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


@admin.register(AuditoriaSeguridad)
class AuditoriaSeguridadAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "accion", "ip")
    list_filter = ("accion", "fecha")
    search_fields = ("usuario__username", "detalle", "ip")
    readonly_fields = ("usuario", "accion", "detalle", "fecha", "ip")
    date_hierarchy = "fecha"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
