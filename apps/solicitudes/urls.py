from django.urls import path

from . import views

app_name = "solicitudes"

urlpatterns = [
    path("", views.ListaSolicitudesView.as_view(), name="lista"),
    path("nueva/", views.CrearSolicitudView.as_view(), name="crear"),
    path("<int:pk>/", views.DetalleSolicitudView.as_view(), name="detalle"),
    path("<int:pk>/asignar-tecnico/", views.AsignarTecnicoView.as_view(), name="asignar_tecnico"),
    path("<int:pk>/estado/", views.CambiarEstadoSolicitudView.as_view(), name="cambiar_estado"),
]