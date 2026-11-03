from django.shortcuts import redirect
from django.urls import reverse


class CambioContrasenaObligatorioMiddleware:
    rutas_permitidas = (
        "/cuentas/ingresar/",
        "/cuentas/salir/",
        "/cuentas/contrasena/",
        "/cuentas/contrasena/actualizada/",
        "/cuentas/recuperar/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and request.user.force_password_change
            and not request.path.startswith(self.rutas_permitidas)
        ):
            return redirect(reverse("password_change"))
        return self.get_response(request)
