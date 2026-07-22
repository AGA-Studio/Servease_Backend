from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework import status

from .models import Usuario
from .serializers import SignupSerializer, UsuarioSerializer
from .supabase_admin import get_supabase_admin, get_supabase_anon

GENERIC_SIGNUP_ERROR = (
    "No pudimos crear tu cuenta. Verifica tus datos e intenta de nuevo."
)
CONFIRMATION_MESSAGE = (
    "Cuenta creada. Revisa tu correo para confirmar tu cuenta antes de iniciar sesión."
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    serializer = UsuarioSerializer(request.user)
    return Response(serializer.data)


class SignupView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'signup'

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            result = get_supabase_anon().auth.sign_up({
                'email': data['email'],
                'password': data['password'],
            })
        except Exception:
            return Response(
                {'detail': GENERIC_SIGNUP_ERROR},
                status=status.HTTP_400_BAD_REQUEST,
            )

        auth_user = result.user
        if auth_user is None:
            return Response(
                {'detail': GENERIC_SIGNUP_ERROR},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Supabase returns a user with no identities when the email already
        # belongs to a confirmed account (anti-enumeration behavior). Reply
        # with the same success message either way so we don't leak whether
        # the email is registered.
        if not auth_user.identities:
            return Response({'detail': CONFIRMATION_MESSAGE}, status=status.HTTP_201_CREATED)

        try:
            Usuario.objects.create(
                id_usuario=auth_user.id,
                nombre=data['nombre'],
                segundo_nombre=data.get('segundo_nombre') or None,
                apellido_pa=data['apellido_pa'],
                apellido_ma=data.get('apellido_ma') or None,
                correo=data['email'],
                rol_id=1,
            )
        except Exception:
            get_supabase_admin().auth.admin.delete_user(auth_user.id)
            return Response(
                {'detail': GENERIC_SIGNUP_ERROR},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({'detail': CONFIRMATION_MESSAGE}, status=status.HTTP_201_CREATED)
