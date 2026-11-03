from django.apps import AppConfig


class CuentasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cuentas"
    label = "cuentas"
    verbose_name = "Cuentas y permisos"

    def ready(self):
        from . import signals
