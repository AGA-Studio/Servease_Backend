from django.urls import path
from . import views

urlpatterns = [
    path('', views.ServicioCreateView.as_view(), name='servicio-create'),
    path('<int:id_servicio>/detalle/', views.PostDetailsView.as_view(), name='servicio-detalle'),
    path('<int:id_servicio>/aplicantes/', views.InfoAplicantesView.as_view(), name='servicio-aplicantes'),
]
