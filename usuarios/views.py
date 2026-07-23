import requests
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework import status
from django.conf import settings

from servicios.models import Servicio
from servicios.serializers import ServicioSerializer
from .models import Usuario, VistaPerfilCliente, VistaReviewsCliente
from .serializers import (
    PerfilClienteSerializer,
    ReviewClienteSerializer,
    SignupSerializer,
    UpdateProfilePhotoSerializer,
    UpdatePersonalInfoSerializer,
    UsuarioSerializer,
)
from .supabase_admin import get_supabase_admin
from .permissions import IsAdminRole, IsClientRole

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

    def delete(self, request):
        """Elimina la cuenta del usuario logueado (cliente o proveedor)."""
        supabase_uid = str(request.user.id_usuario)
        try:
            get_supabase_admin().auth.admin.delete_user(supabase_uid)
        except Exception:
            return Response(
                {'detail': 'No se pudo eliminar la cuenta. Intenta de nuevo.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        # public.usuario se borra solo por el ON DELETE CASCADE hacia auth.users
        return Response(status=status.HTTP_204_NO_CONTENT)


class UpdatePersonalInfoView(APIView):
    """Modificar nombre, apellidos, celular — solo rol cliente."""
    permission_classes = [IsAuthenticated, IsClientRole]

    def patch(self, request):
        serializer = UpdatePersonalInfoSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UsuarioSerializer(request.user).data)


class RequestPasswordResetView(APIView):
    """Dispara el correo de restablecimiento de contraseña de Supabase."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        url = f"{settings.SUPABASE_URL}/auth/v1/recover"
        headers = {"apikey": settings.SUPABASE_ANON_KEY, "Content-Type": "application/json"}
        try:
            response = requests.post(
                url, json={"email": request.user.correo}, headers=headers, timeout=10
            )
            response.raise_for_status()
        except requests.RequestException:
            return Response(
                {'detail': 'No se pudo enviar el correo de restablecimiento.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({'detail': 'Correo de restablecimiento enviado.'})


class MfaEnrollView(APIView):
    """Inicia el registro de 2FA (TOTP): regresa QR/secret."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        url = f"{settings.SUPABASE_URL}/auth/v1/factors"
        headers = {
            "apikey": settings.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {request.auth}",
            "Content-Type": "application/json",
        }
        body = {"factor_type": request.data.get('factor_type', 'totp')}
        try:
            response = requests.post(url, json=body, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            return Response(
                {'detail': 'No se pudo iniciar el registro de 2FA.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(response.json())


class MfaChallengeView(APIView):
    """Crea el challenge para verificar el factor recién registrado."""
    permission_classes = [IsAuthenticated]

    def post(self, request, factor_id):
        url = f"{settings.SUPABASE_URL}/auth/v1/factors/{factor_id}/challenge"
        headers = {
            "apikey": settings.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {request.auth}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(url, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            return Response(
                {'detail': 'No se pudo crear el challenge de 2FA.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(response.json())


class MfaVerifyView(APIView):
    """Verifica el código TOTP ingresado por el usuario."""
    permission_classes = [IsAuthenticated]

    def post(self, request, factor_id):
        code = request.data.get('code')
        challenge_id = request.data.get('challenge_id')
        if not code or not challenge_id:
            return Response(
                {'detail': 'code y challenge_id son requeridos.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        url = f"{settings.SUPABASE_URL}/auth/v1/factors/{factor_id}/verify"
        headers = {
            "apikey": settings.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {request.auth}",
            "Content-Type": "application/json",
        }
        body = {"code": code, "challenge_id": challenge_id}
        try:
            response = requests.post(url, json=body, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            return Response(
                {'detail': 'Código inválido o expirado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(response.json())


class DisableUserView(APIView):
    """Deshabilita a un usuario. Solo administradores."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, id_usuario):
        try:
            usuario = Usuario.objects.get(pk=id_usuario)
        except Usuario.DoesNotExist:
            return Response({'detail': 'Usuario no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        usuario.estado = False
        usuario.save(update_fields=['estado'])
        return Response(UsuarioSerializer(usuario).data)


class PerfilClienteView(RetrieveAPIView):
    """Perfil público de un cliente (datos generales + rating)."""
    permission_classes = [IsAuthenticated]
    serializer_class = PerfilClienteSerializer
    queryset = VistaPerfilCliente.objects.all()
    lookup_field = 'id_usuario'
    lookup_url_kwarg = 'id_usuario'


class ReviewsClienteView(ListAPIView):
    """Reviews recibidas por un cliente, más recientes primero."""
    permission_classes = [IsAuthenticated]
    serializer_class = ReviewClienteSerializer

    def get_queryset(self):
        return VistaReviewsCliente.objects.filter(
            cliente_id=self.kwargs['id_usuario']
        ).order_by('-fecha')


class UltimasPublicacionesClienteView(ListAPIView):
    """Últimas 5 publicaciones (servicios) de un cliente."""
    permission_classes = [IsAuthenticated]
    serializer_class = ServicioSerializer

    def get_queryset(self):
        return Servicio.objects.raw(
            'SELECT * FROM ultimas_publicaciones_cliente(%s)',
            [str(self.kwargs['id_usuario'])],
        )


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