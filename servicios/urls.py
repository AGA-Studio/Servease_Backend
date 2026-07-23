from django.urls import path
from . import views

urlpatterns = [
    path('', views.ServicioCreateView.as_view(), name='servicio-create'),
]
