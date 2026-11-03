from django.urls import path

from . import views

app_name = "equipos"

urlpatterns = [
    path("", views.ListaEquiposView.as_view(), name="lista"),
    path("nuevo/", views.CrearEquipoView.as_view(), name="crear"),
    path("categorias/", views.ListaCategoriasView.as_view(), name="categorias"),
    path("categorias/nueva/", views.CrearCategoriaView.as_view(), name="categoria_crear"),
    path("categorias/<int:pk>/desactivar/", views.DesactivarCategoriaView.as_view(), name="categoria_desactivar"),
    path("<int:pk>/", views.FichaEquipoView.as_view(), name="ficha"),
    path("<int:pk>/editar/", views.EditarEquipoView.as_view(), name="editar"),
    path("<int:pk>/dar-de-baja/", views.BajaEquipoView.as_view(), name="baja"),
]