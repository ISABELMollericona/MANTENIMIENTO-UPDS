from django.urls import path

from . import views

app_name = "intervenciones"

urlpatterns = [
    path("mis-tareas/", views.MisTareasView.as_view(), name="mis_tareas"),
    path("solicitud/<int:solicitud_id>/nueva/", views.CrearIntervencionView.as_view(), name="crear"),
]