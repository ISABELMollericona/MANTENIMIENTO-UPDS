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
