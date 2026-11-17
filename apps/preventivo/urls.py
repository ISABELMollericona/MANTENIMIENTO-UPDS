from django.urls import path

from . import views

app_name = "preventivo"

urlpatterns = [
    path("", views.CronogramaView.as_view(), name="cronograma"),
    path("cargar/", views.CargarCronogramaView.as_view(), name="cargar"),
    path("<int:pk>/realizado/", views.MarcarRealizadoView.as_view(), name="marcar"),
    path("<int:pk>/pendiente/", views.MarcarPendienteView.as_view(), name="pendiente"),
]
