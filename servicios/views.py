from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from usuarios.permissions import IsClientRole
from .models import Servicio, VistaInfoAplicantes, VistaPostDetails
from .serializers import (
    CreateServicioSerializer,
    InfoAplicanteSerializer,
    PostDetailsSerializer,
    ServicioSerializer,
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
