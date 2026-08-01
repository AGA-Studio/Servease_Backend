from django.urls import path

from .views import (
    DashboardPostDetailsView,
    DashboardProveedorView,
    DashboardTrabajosDisponiblesView,
)

urlpatterns = [
    path('proveedor/<uuid:proveedor_id>/', DashboardProveedorView.as_view(), name='dashboard-proveedor'),
    path('post-details/<int:id_servicio>/', DashboardPostDetailsView.as_view(), name='dashboard-post-details'),
    path('trabajos-disponibles/', DashboardTrabajosDisponiblesView.as_view(), name='dashboard-trabajos-disponibles'),
]
