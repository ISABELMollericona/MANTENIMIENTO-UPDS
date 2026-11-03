from django.urls import path

from . import views

app_name = "preventivo"

urlpatterns = [
    path("", views.ListaProgramacionesView.as_view(), name="programaciones"),
    path("nueva/", views.CrearProgramacionView.as_view(), name="programar"),
    path("completar/<int:pk>/", views.CompletarProgramacionView.as_view(), name="completar"),
    path("cancelar/<int:pk>/", views.CancelarProgramacionView.as_view(), name="cancelar"),
    path("planes/", views.ListaPlanesView.as_view(), name="planes"),
    path("planes/nuevo/", views.CrearPlanView.as_view(), name="plan_crear"),
    path("planes/<int:pk>/editar/", views.EditarPlanView.as_view(), name="plan_editar"),
]