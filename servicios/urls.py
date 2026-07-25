from django.urls import path
from . import views

# urlpatterns = [
#     path('', views.ServicioCreateView.as_view(), name='servicio-create'),
#     path('<int:id_servicio>/detalle/', views.PostDetailsView.as_view(), name='servicio-detalle'),
#     path('<int:id_servicio>/aplicantes/', views.InfoAplicantesView.as_view(), name='servicio-aplicantes'),
# ]


urlpatterns = [
    path('', views.ServicioListView.as_view(), name='servicio-list'),
    path('crear/', views.ServicioCreateView.as_view(), name='servicio-create'),
    path('<int:id_servicio>/editar/', views.ServicioEditView.as_view(), name='servicio-edit'),
    path('<int:id_servicio>/eliminar/', views.ServicioDeleteView.as_view(), name='servicio-delete'),
    path('<int:id_servicio>/detalle/', views.PostDetailsView.as_view(), name='servicio-detalle'),
    path('<int:id_servicio>/aplicantes/', views.InfoAplicantesView.as_view(), name='servicio-aplicantes'),
]