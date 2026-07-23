from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from usuarios.permissions import IsClientRole
from .serializers import CreateServicioSerializer, ServicioSerializer


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
