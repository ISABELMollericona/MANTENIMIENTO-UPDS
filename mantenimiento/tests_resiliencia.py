from unittest import mock

from django.db import OperationalError
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from django.core.handlers.exception import convert_exception_to_response

from mantenimiento.db_resiliencia import ReintentoBaseDatosMiddleware


class ConfiguracionBaseDatosTests(SimpleTestCase):
    def test_settings_activa_health_checks_para_postgres(self):
        import importlib
        import mantenimiento.settings as settings_mod

        url = "postgresql://u:p@ejemplo-pooler.neon.tech/db?sslmode=require"
        with mock.patch.dict("os.environ", {"DATABASE_URL": url}), mock.patch("sys.argv", ["manage.py", "runserver"]):
            recargado = importlib.reload(settings_mod)
        try:
            db = recargado.DATABASES["default"]
            self.assertTrue(db["CONN_HEALTH_CHECKS"])
            self.assertTrue(db["DISABLE_SERVER_SIDE_CURSORS"])
            self.assertLessEqual(db["CONN_MAX_AGE"], 60)
            self.assertEqual(db["OPTIONS"]["connect_timeout"], 10)
        finally:
            importlib.reload(settings_mod)

    def test_logging_envia_errores_a_consola(self):
        from django.conf import settings

        self.assertIn("console", settings.LOGGING["loggers"]["django.request"]["handlers"])


class ReintentoBaseDatosMiddlewareTests(SimpleTestCase):
    def _middleware(self, vista):
        return ReintentoBaseDatosMiddleware(convert_exception_to_response(vista))

    def test_reintenta_get_tras_error_transitorio(self):
        llamadas = []

        def vista(request):
            llamadas.append(1)
            if len(llamadas) == 1:
                raise OperationalError("server closed the connection unexpectedly")
            return HttpResponse("ok")

        with self.assertLogs("django.request", "ERROR"):
            respuesta = self._middleware(vista)(RequestFactory().get("/"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(llamadas), 2)

    def test_no_reintenta_post(self):
        llamadas = []

        def vista(request):
            llamadas.append(1)
            raise OperationalError("server closed the connection unexpectedly")

        with self.assertLogs("django.request", "ERROR"):
            respuesta = self._middleware(vista)(RequestFactory().post("/"))
        self.assertEqual(respuesta.status_code, 500)
        self.assertEqual(len(llamadas), 1)

    def test_no_reintenta_otros_errores(self):
        llamadas = []

        def vista(request):
            llamadas.append(1)
            raise ValueError("bug")

        with self.assertLogs("django.request", "ERROR"):
            respuesta = self._middleware(vista)(RequestFactory().get("/"))
        self.assertEqual(respuesta.status_code, 500)
        self.assertEqual(len(llamadas), 1)

    def test_pagina_500_personalizada(self):
        from django.template.loader import render_to_string

        html = render_to_string("500.html")
        self.assertIn("Reintentar", html)
