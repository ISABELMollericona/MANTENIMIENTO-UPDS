from pathlib import Path

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import FileResponse
from django.urls import include, path
from django.views.generic import TemplateView

from apps.cuentas.auth_views import CambioContrasenaView, RestablecerContrasenaConfirmView
from apps.panel.views import PanelInicioView, keepalive
from mantenimiento.offline import catalogos_offline, sincronizar_offline

BASE_DIR = Path(__file__).resolve().parent.parent


def _static_file_response(path_name, content_type):
    file_path = BASE_DIR / "static" / path_name
    response = FileResponse(file_path.open("rb"), content_type=content_type)
    response["Cache-Control"] = "no-cache"
    return response


def manifest_webmanifest(request):
    return _static_file_response("manifest.webmanifest", "application/manifest+json")


def service_worker(request):
    response = _static_file_response("service-worker.js", "application/javascript")
    response["Service-Worker-Allowed"] = "/"
    return response


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/keepalive/", keepalive, name="keepalive"),
    path("api/offline/catalogos/", catalogos_offline, name="offline_catalogos"),
    path("api/offline/sincronizar/", sincronizar_offline, name="offline_sincronizar"),
    path("manifest.webmanifest", manifest_webmanifest, name="manifest"),
    path("service-worker.js", service_worker, name="service_worker"),
    path("offline.html", TemplateView.as_view(template_name="offline.html"), name="offline_page"),
    path("cuentas/", include("apps.cuentas.urls")),
    path("ambientes/", include("apps.ubicaciones.urls")),
    path("equipos/", include("apps.equipos.urls")),
    path("solicitudes/", include("apps.solicitudes.urls")),
    path("intervenciones/", include("apps.intervenciones.urls")),
    path("preventivo/", include("apps.preventivo.urls")),
    path("reportes/", include("apps.reportes.urls")),
    path("", PanelInicioView.as_view(), name="panel"),
    path("cuentas/ingresar/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("cuentas/salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("cuentas/contrasena/", CambioContrasenaView.as_view(template_name="registration/password_change_form.html"), name="password_change"),
    path("cuentas/contrasena/actualizada/", auth_views.PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"), name="password_change_done"),
    path("cuentas/recuperar/", auth_views.PasswordResetView.as_view(template_name="registration/password_reset_form.html"), name="password_reset"),
    path("cuentas/recuperar/enviado/", auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"), name="password_reset_done"),
    path("cuentas/recuperar/confirmar/<uidb64>/<token>/", RestablecerContrasenaConfirmView.as_view(template_name="registration/password_reset_confirm.html"), name="password_reset_confirm"),
    path("cuentas/recuperar/completado/", auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"), name="password_reset_complete"),
]
