from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import TemplateView

from apps.cuentas.auth_views import CambioContrasenaView, RestablecerContrasenaConfirmView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuentas/", include("apps.cuentas.urls")),
    path("", TemplateView.as_view(template_name="panel/inicio.html"), name="panel"),
    path("cuentas/ingresar/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("cuentas/salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("cuentas/contrasena/", CambioContrasenaView.as_view(template_name="registration/password_change_form.html"), name="password_change"),
    path("cuentas/contrasena/actualizada/", auth_views.PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"), name="password_change_done"),
    path("cuentas/recuperar/", auth_views.PasswordResetView.as_view(template_name="registration/password_reset_form.html"), name="password_reset"),
    path("cuentas/recuperar/enviado/", auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"), name="password_reset_done"),
    path("cuentas/recuperar/confirmar/<uidb64>/<token>/", RestablecerContrasenaConfirmView.as_view(template_name="registration/password_reset_confirm.html"), name="password_reset_confirm"),
    path("cuentas/recuperar/completado/", auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"), name="password_reset_complete"),
]
