from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "cuentas"

urlpatterns = [
    path("usuarios/", views.ListaUsuariosView.as_view(), name="usuarios"),
    path("usuarios/nuevo/", views.CrearUsuarioView.as_view(), name="usuario_crear"),
    path("usuarios/<int:pk>/editar/", views.EditarUsuarioView.as_view(), name="usuario_editar"),
    path("roles/", views.ListaRolesView.as_view(), name="roles"),
    path("roles/nuevo/", views.CrearRolView.as_view(), name="rol_crear"),
    path("roles/<int:pk>/editar/", views.EditarRolView.as_view(), name="rol_editar"),
    path("roles/<int:pk>/eliminar/", views.EliminarRolView.as_view(), name="rol_eliminar"),
    path("ingresar/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
]
