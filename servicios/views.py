from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated

from usuarios.permissions import IsClientRole
from .models import Servicio, VistaInfoAplicantes, VistaPostDetails
from .serializers import (
    CreateServicioSerializer,
    InfoAplicanteSerializer,
    PostDetailsSerializer,
    ServicioListSerializer,
    ServicioSerializer,
    UpdateServicioSerializer,
)

class ServicioCreateView(APIView):
    """Crea una nueva solicitud de servicio. Solo rol cliente."""
    permission_classes = [IsAuthenticated, IsClientRole]

    def post(self, request):
        serializer = CreateServicioSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        servicio = serializer.save()
        return Response(
            ServicioSerializer(servicio).data, status=status.HTTP_201_CREATED
        )


class ServicioEditView(APIView):
    """Edita una publicacion. Solo el cliente dueño, y solo si sigue 'abierto'."""
    permission_classes = [IsAuthenticated, IsClientRole]

    def patch(self, request, id_servicio):
        servicio = get_object_or_404(Servicio, pk=id_servicio)

        if servicio.cliente_id != request.user.id_usuario:
            raise PermissionDenied('No puedes editar un servicio que no es tuyo.')
        if servicio.estado != 'abierto':
            raise PermissionDenied(
                'Solo puedes editar publicaciones que sigan abiertas.'
            )

        serializer = UpdateServicioSerializer(
            servicio, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ServicioSerializer(servicio).data)
    
class ServicioDeleteView(APIView):
    """Cancela una publicacion (borrado logico). Solo el cliente dueño, y solo si sigue 'abierto'."""
    permission_classes = [IsAuthenticated, IsClientRole]

    def delete(self, request, id_servicio):
        servicio = get_object_or_404(Servicio, pk=id_servicio)

        if servicio.cliente_id != request.user.id_usuario:
            raise PermissionDenied('No puedes eliminar un servicio que no es tuyo.')
        if servicio.estado != 'abierto':
            raise PermissionDenied(
                'Solo puedes eliminar publicaciones que sigan abiertas.'
            )

        servicio.estado = 'cancelado'
        servicio.save(update_fields=['estado'])
        return Response(
            {'detail': 'La publicación se canceló correctamente.'},
            status=status.HTTP_200_OK,
        )
class PostDetailsView(RetrieveAPIView):
    """Detalle de un servicio publicado, con la info del cliente que lo pidió."""
    permission_classes = [IsAuthenticated]
    serializer_class = PostDetailsSerializer
    queryset = VistaPostDetails.objects.all()
    lookup_field = 'id_servicio'
    lookup_url_kwarg = 'id_servicio'


class InfoAplicantesView(ListAPIView):
    """Postulaciones a un servicio. Solo el cliente dueño del servicio puede verlas."""
    permission_classes = [IsAuthenticated]
    serializer_class = InfoAplicanteSerializer

    def get_queryset(self):
        servicio_id = self.kwargs['id_servicio']
        servicio = get_object_or_404(Servicio, pk=servicio_id)
        if servicio.cliente_id != self.request.user.id_usuario:
            raise PermissionDenied(
                'No puedes ver los aplicantes de un servicio que no es tuyo.'
            )
        return VistaInfoAplicantes.objects.filter(servicio_id=servicio_id)


class ServicioListView(ListAPIView):
    """Catalogo publico de servicios, filtrable por categoria y estado."""
    permission_classes = [AllowAny]
    serializer_class = ServicioListSerializer
    queryset = Servicio.objects.exclude(estado='cancelado').order_by('-fecha')
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['categoria_id', 'estado']