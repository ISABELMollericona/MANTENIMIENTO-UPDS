from django.urls import path

from .views import ReportesView

app_name = "reportes"

urlpatterns = [path("", ReportesView.as_view(), name="lista")]