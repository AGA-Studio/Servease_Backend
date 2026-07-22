from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework import status

from .models import Usuario
from .serializers import (
    SignupSerializer,
    UpdateProfilePhotoSerializer,
    UsuarioSerializer,
)
from .supabase_admin import get_supabase_admin

GENERIC_SIGNUP_ERROR = (
    "No pudimos crear tu cuenta. Verifica tus datos e intenta de nuevo."
)
SIGNUP_SUCCESS_MESSAGE = "Cuenta creada correctamente."


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UsuarioSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UpdateProfilePhotoSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        request.user.url_foto_perfil = serializer.validated_data['url_foto_perfil']
        request.user.save(update_fields=['url_foto_perfil'])
        return Response(UsuarioSerializer(request.user).data)


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
            # Cuenta creada ya confirmada: por ahora no se envía correo de
            # confirmación, así que el usuario puede iniciar sesión de inmediato.
            result = get_supabase_admin().auth.admin.create_user({
                'email': data['email'],
                'password': data['password'],
                'email_confirm': True,
                'user_metadata': {
                    'first_name': data['nombre'],
                    'last_name_p': data['apellido_pa'],
                    'last_name_m': data.get('apellido_ma') or '',
                },
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

        return Response({'detail': SIGNUP_SUCCESS_MESSAGE}, status=status.HTTP_201_CREATED)
