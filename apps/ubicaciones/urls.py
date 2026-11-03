from django.urls import path

from . import views

app_name = "ubicaciones"

urlpatterns = [
    path("", views.ListaAmbientesView.as_view(), name="lista"),
    path("nuevo/", views.CrearAmbienteView.as_view(), name="crear"),
    path("<int:pk>/editar/", views.EditarAmbienteView.as_view(), name="editar"),
    path("<int:pk>/dar-de-baja/", views.DesactivarAmbienteView.as_view(), name="desactivar"),
]