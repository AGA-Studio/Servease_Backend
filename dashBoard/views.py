from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import VistaDashboardProveedor, VistaPostDetails, VistaTrabajosDisponibles
from .serializers import (
    DashboardPostDetailsSerializer,
    DashboardProveedorSerializer,
    DashboardTrabajosDisponiblesSerializer,
)


class DashboardProveedorView(APIView):
    """Dashboard del proveedor para ver métricas resumidas."""
    permission_classes = [IsAuthenticated]

    def get(self, request, proveedor_id):
        dashboard = get_object_or_404(VistaDashboardProveedor, pk=proveedor_id)

        if str(request.user.id_usuario) != str(dashboard.proveedor_id):
            raise PermissionDenied('No tienes permiso para ver este dashboard.')

        serializer = DashboardProveedorSerializer(dashboard)
        return Response(serializer.data)


class DashboardPostDetailsView(APIView):
    """Detalle de un servicio publicado para la vista de dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request, id_servicio):
        post = get_object_or_404(VistaPostDetails, pk=id_servicio)
        serializer = DashboardPostDetailsSerializer(post)
        return Response(serializer.data)


class DashboardTrabajosDisponiblesView(APIView):
    """Lista de trabajos disponibles para el dashboard del proveedor."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = VistaTrabajosDisponibles.objects.all().order_by('-fecha')

        categoria_id = request.query_params.get('categoria_id')
        if categoria_id:
            queryset = queryset.filter(categoria_id=categoria_id)

        serializer = DashboardTrabajosDisponiblesSerializer(queryset, many=True)
        return Response(serializer.data)
