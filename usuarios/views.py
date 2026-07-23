import logging

from django.conf import settings
from django.core import signing
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework import status

from .emails import send_confirmation_email
from .models import Usuario
from .serializers import (
    SignupSerializer,
    UpdateProfilePhotoSerializer,
    UsuarioSerializer,
)
from .storage import delete_profile_photos, upload_profile_photo
from .supabase_admin import get_supabase_admin
from .tokens import make_confirmation_token, verify_confirmation_token

logger = logging.getLogger(__name__)

GENERIC_SIGNUP_ERROR = (
    "No pudimos crear tu cuenta. Verifica tus datos e intenta de nuevo."
)
EMAIL_SEND_ERROR = (
    "No pudimos enviarte el correo de confirmación. Intenta de nuevo."
)
SIGNUP_SUCCESS_MESSAGE = (
    "Cuenta creada. Revisa tu correo para confirmarla antes de iniciar sesión."
)


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
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'signup'

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            # email_confirm=True: Supabase's own confirmation flow is
            # bypassed, we run our own via `estado` + Resend below.
            result = get_supabase_admin().auth.admin.create_user({
                'email': data['email'],
                'password': data['password'],
                'email_confirm': True,
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

        photo_url = None
        photo = data.get('photo')
        if photo:
            try:
                photo_url = upload_profile_photo(auth_user.id, photo)
            except Exception:
                # Decorative and optional: don't fail signup over it.
                logger.exception('profile photo upload failed for signup')

        try:
            Usuario.objects.create(
                id_usuario=auth_user.id,
                nombre=data['nombre'],
                segundo_nombre=data.get('segundo_nombre') or None,
                apellido_pa=data['apellido_pa'],
                apellido_ma=data.get('apellido_ma') or None,
                correo=data['email'],
                rol_id=1,
                estado=False,
                url_foto_perfil=photo_url,
            )
        except Exception:
            get_supabase_admin().auth.admin.delete_user(auth_user.id)
            delete_profile_photos(auth_user.id)
            return Response(
                {'detail': GENERIC_SIGNUP_ERROR},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        token = make_confirmation_token(auth_user.id)
        confirm_url = f'{settings.FRONTEND_URL}/confirm-email?token={token}'

        try:
            send_confirmation_email(data['email'], confirm_url)
        except Exception:
            Usuario.objects.filter(pk=auth_user.id).delete()
            get_supabase_admin().auth.admin.delete_user(auth_user.id)
            delete_profile_photos(auth_user.id)
            return Response(
                {'detail': EMAIL_SEND_ERROR},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({'detail': SIGNUP_SUCCESS_MESSAGE}, status=status.HTTP_201_CREATED)


class ConfirmEmailView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'confirm-email'

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response(
                {'detail': 'Falta el token de confirmación.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_id = verify_confirmation_token(token)
        except signing.SignatureExpired:
            return Response(
                {'detail': 'El enlace de confirmación expiró. Vuelve a registrarte.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except signing.BadSignature:
            return Response(
                {'detail': 'Enlace de confirmación inválido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            usuario = Usuario.objects.get(pk=user_id)
        except Usuario.DoesNotExist:
            return Response(
                {'detail': 'Enlace de confirmación inválido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not usuario.estado:
            usuario.estado = True
            usuario.save(update_fields=['estado'])

        return Response({'detail': 'Cuenta confirmada. Ya puedes iniciar sesión.'})
