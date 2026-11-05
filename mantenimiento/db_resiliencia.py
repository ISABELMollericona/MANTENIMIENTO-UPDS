"""Reintento automático ante cortes transitorios de la base de datos.

Neon (PostgreSQL serverless) suspende el cómputo por inactividad y cierra las
conexiones. Si una petición de lectura falla por ese motivo, se cierran las
conexiones y se reintenta UNA vez, en lugar de mostrar "Server Error (500)".
Solo se reintentan métodos seguros (GET/HEAD/OPTIONS), que no modifican datos.
"""

import logging

from django.core.signals import got_request_exception
from django.db import InterfaceError, OperationalError, connections

logger = logging.getLogger(__name__)

METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}
ERRORES_TRANSITORIOS = (OperationalError, InterfaceError)


def _marcar_error_bd(sender, request=None, **kwargs):
    import sys

    exc = sys.exc_info()[1]
    if request is not None and isinstance(exc, ERRORES_TRANSITORIOS):
        request._error_bd_transitorio = exc


got_request_exception.connect(_marcar_error_bd, dispatch_uid="db_resiliencia_marcar_error")


def _cerrar_conexiones():
    for conn in connections.all(initialized_only=True):
        try:
            conn.close()
        except Exception:  # la conexión ya estaba rota
            pass


def salud(request):
    """Diagnóstico público de la base de datos (sin hosts, usuarios ni contraseñas).

    Responde 200 si la base de datos contesta y tiene las tablas de Django, y 503 si no.
    Sirve para el health check de Render y para diagnosticar errores 500.
    """
    from django.db import connection
    from django.http import JsonResponse

    datos = {"motor": connection.vendor, "base_de_datos": "ok"}
    estado = 200
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        tablas = set(connection.introspection.table_names())
        faltantes = sorted({"django_session", "django_migrations"} - tablas)
        if faltantes:
            datos.update(base_de_datos="sin_tablas", faltan=faltantes, ayuda="Ejecuta python manage.py migrate en esta base de datos.")
            estado = 503
    except Exception as exc:  # noqa: BLE001 - se informa el tipo de error, no el detalle
        logger.exception("Health check de base de datos falló")
        datos.update(base_de_datos="error", error=type(exc).__name__)
        estado = 503
        _cerrar_conexiones()
    response = JsonResponse(datos, status=estado)
    response["Cache-Control"] = "no-store"
    return response


class ReintentoBaseDatosMiddleware:
    """Debe ir primero en MIDDLEWARE para cubrir también sesiones y autenticación."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        error = getattr(request, "_error_bd_transitorio", None)
        if response.status_code >= 500 and error is not None:
            _cerrar_conexiones()
            if request.method in METODOS_SEGUROS:
                logger.warning("Error transitorio de base de datos en %s; reintentando: %s", request.path, error)
                request._error_bd_transitorio = None
                for attr in ("_cached_user", "user", "session"):
                    request.__dict__.pop(attr, None)
                response = self.get_response(request)
                if getattr(request, "_error_bd_transitorio", None) is not None:
                    _cerrar_conexiones()
        return response
