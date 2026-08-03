from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.exceptions import ValidationError
from usuarios.permissions import IsProviderRole 
from usuarios.permissions import IsClientRole
from .models import Servicio, VistaInfoAplicantes, VistaPostDetails,Postulacion  
from .models.estado import ABIERTO, CANCELADO, PENDIENTE
from .serializers import (
    CreateServicioSerializer,
    InfoAplicanteSerializer,
    OfertaSerializer,
    PostDetailsSerializer,
    ServicioListSerializer,
    ServicioSerializer,
    UpdateServicioSerializer,
    CreateOfertaSerializer,
    PostulacionSerializer,
    CreatePostulacionSerializer,  
)


class ServicioCreateView(APIView):
    """Crea una nueva solicitud de servicio. Solo rol cliente."""
    permission_classes = [IsAuthenticated, IsClientRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'servicio-create'

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
        if servicio.estado_id != ABIERTO:
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
        if servicio.estado_id != ABIERTO:
            raise PermissionDenied(
                'Solo puedes eliminar publicaciones que sigan abiertas.'
            )

        servicio.estado_id = CANCELADO
        servicio.save(update_fields=['estado_id'])
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
    queryset = Servicio.objects.exclude(estado_id=CANCELADO).order_by('-fecha')
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['categoria_id', 'estado']


class OfertaCreateView(APIView):
    """Envia una oferta/contraoferta. Solo cliente dueño o proveedor de la postulacion."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'oferta-create'

    def post(self, request):
        serializer = CreateOfertaSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        oferta = serializer.save()
        return Response(OfertaSerializer(oferta).data, status=status.HTTP_201_CREATED)

class PostularServicioView(APIView):
    """Un proveedor se postula a un servicio abierto."""
    permission_classes = [IsAuthenticated, IsProviderRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'postulacion-create'
 
    def post(self, request, id_servicio):
        servicio = get_object_or_404(Servicio, pk=id_servicio)
 
        if servicio.estado_id != ABIERTO:
            raise ValidationError('Este servicio ya no acepta postulaciones.')
 
        if servicio.cliente_id == request.user.id_usuario:
            raise PermissionDenied('No puedes postularte a tu propio servicio.')
 
        if Postulacion.objects.filter(servicio=servicio, proveedor=request.user).exists():
            raise ValidationError('Ya te postulaste a este servicio.')
 
        serializer = CreatePostulacionSerializer(
            data=request.data,
            context={'request': request, 'servicio': servicio}
        )
        serializer.is_valid(raise_exception=True)
        postulacion = serializer.save()
        return Response(
            PostulacionSerializer(postulacion).data, status=status.HTTP_201_CREATED
        )
 