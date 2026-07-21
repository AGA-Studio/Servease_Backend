from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializers import UsuarioSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    serializer = UsuarioSerializer(request.user)
    return Response(serializer.data)
