import hashlib
import hmac
import logging
import secrets

import requests
from django.conf import settings
from django.core import signing
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework import status


from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from servicios.models import Servicio
from servicios.serializers import ServicioListSerializer

from servicios.models import Servicio
from servicios.serializers import ServicioSerializer
from .emails import send_confirmation_email
from .models import (
    Categoria,
    Usuario,
    VistaPerfilCliente,
    VistaReviewsCliente,
    VistaHomeCliente,
    VistaResumenGanancias,
    VistaTrabajosAplicados,
    VistaTrabajosDisponibles,
    VistaUltimaResena,
    Notificacion,
    MfaBackupCode,
    PortafolioProveedor,  
)
from .permissions import IsAdminRole, IsClientRole
from .serializers import (
    CategoriaSerializer,
    HomeClienteSerializer,
    PerfilClienteSerializer,
    ReviewClienteSerializer,
    SignupSerializer,
    UpdateProfilePhotoSerializer,
    UpdatePersonalInfoSerializer,
    UsuarioSerializer,
    DisponibilidadSerializer,
    AreasTrabajoSerializer,
    ResumenGananciasSerializer,
    TrabajoAplicadoSerializer,
    TrabajoAplicadoCardSerializer,
    TrabajoDisponibleSerializer,
    UltimaResenaSerializer,
    NotificacionSerializer,
    PortafolioSerializer,
    CreatePortafolioSerializer,  

)
from .storage import delete_profile_photos, upload_profile_photo
from .supabase_admin import get_supabase_admin
from .tokens import make_confirmation_token, verify_confirmation_token

from .permissions import IsProviderRole  # ver  si es correcto

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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password-reset'

    def post(self, request):
        url = f"{settings.SUPABASE_URL}/auth/v1/recover"
        headers = {"apikey": settings.SUPABASE_ANON_KEY, "Content-Type": "application/json"}
        params = {"redirect_to": f"{settings.FRONTEND_URL}/reset-password"}
        try:
            response = requests.post(
                url,
                params=params,
                json={"email": request.user.correo},
                headers=headers,
                timeout=10,
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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'mfa-enroll'

    def post(self, request):
        url = f"{settings.SUPABASE_URL}/auth/v1/factors"
        headers = {
            "apikey": settings.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {request.auth}",
            "Content-Type": "application/json",
        }
        body = {"factor_type": request.data.get('factor_type', 'totp')}
        friendly_name = request.data.get('friendly_name')
        if friendly_name:
            body['friendly_name'] = friendly_name
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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'mfa-challenge'

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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'mfa-verify'

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


_BACKUP_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_BACKUP_CODE_COUNT = 8


def _generate_backup_code() -> str:
    raw = ''.join(secrets.choice(_BACKUP_CODE_ALPHABET) for _ in range(10))
    return f"{raw[:5]}-{raw[5:]}"


def _hash_backup_code(code: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256
    ).hexdigest()


class MfaBackupCodesGenerateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'mfa-backup-generate'

    def post(self, request):
        MfaBackupCode.objects.filter(
            usuario=request.user, used_at__isnull=True
        ).delete()

        codes = [_generate_backup_code() for _ in range(_BACKUP_CODE_COUNT)]
        MfaBackupCode.objects.bulk_create([
            MfaBackupCode(usuario=request.user, code_hash=_hash_backup_code(code))
            for code in codes
        ])

        return Response({'codes': codes})


class MfaBackupCodeVerifyView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'mfa-backup-verify'

    def post(self, request):
        code = (request.data.get('code') or '').strip().upper()
        if not code:
            return Response(
                {'detail': 'code es requerido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code_hash = _hash_backup_code(code)
        try:
            backup_code = MfaBackupCode.objects.get(
                usuario=request.user, code_hash=code_hash, used_at__isnull=True,
            )
        except MfaBackupCode.DoesNotExist:
            return Response(
                {'detail': 'Código inválido o ya utilizado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        backup_code.used_at = timezone.now()
        backup_code.save(update_fields=['used_at'])

        remaining = MfaBackupCode.objects.filter(
            usuario=request.user, used_at__isnull=True,
        ).count()
        return Response({'detail': 'Código válido.', 'remaining': remaining})


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


class CategoriaListView(ListAPIView):
    """Lista todas las categorías (solo id y nombre)."""
    permission_classes = [IsAuthenticated]
    serializer_class = CategoriaSerializer
    queryset = Categoria.objects.all()


class CategoriaDetailView(RetrieveAPIView):
    """Detalle de una categoría por id (solo id y nombre)."""
    permission_classes = [IsAuthenticated]
    serializer_class = CategoriaSerializer
    queryset = Categoria.objects.all()
    lookup_field = 'id_categoria'
    lookup_url_kwarg = 'id_categoria'


class PerfilClienteView(RetrieveAPIView):
    """Perfil público de un cliente (datos generales + rating)."""
    permission_classes = [IsAuthenticated]
    serializer_class = PerfilClienteSerializer
    queryset = VistaPerfilCliente.objects.all()
    lookup_field = 'id_usuario'
    lookup_url_kwarg = 'id_usuario'


class HomeClienteView(ListAPIView):
    """Servicios recomendados para la pantalla de inicio del cliente."""
    permission_classes = [IsAuthenticated]
    serializer_class = HomeClienteSerializer

    def get_queryset(self):
        return VistaHomeCliente.objects.filter(
            cliente_id=self.kwargs['id_usuario']
        )


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
        id_usuario = self.kwargs['id_usuario']
        if str(self.request.user.id_usuario) != str(id_usuario):
            raise PermissionDenied(
                'No puedes ver las publicaciones de otro usuario.'
            )
        return Servicio.objects.raw(
            'SELECT * FROM ultimas_publicaciones_cliente(%s)',
            [str(id_usuario)],
        )

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

class MisPublicacionesPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


class MisPublicacionesView(ListAPIView):
    """Todas las publicaciones de un cliente, paginadas y filtrables."""
    permission_classes = [IsAuthenticated]
    serializer_class = ServicioListSerializer
    pagination_class = MisPublicacionesPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['estado', 'categoria_id']

    def get_queryset(self):
        id_usuario = self.kwargs['id_usuario']
        if str(self.request.user.id_usuario) != str(id_usuario):
            raise PermissionDenied(
                'No puedes ver las publicaciones de otro usuario.'
            )
        return Servicio.objects.filter(cliente_id=id_usuario).order_by('-fecha')


class DisponibilidadView(APIView):
    """Ver/cambiar el estado 'disponible para trabajar'. Solo proveedores."""
    permission_classes = [IsAuthenticated, IsProviderRole]
 
    def get(self, request):
        return Response(DisponibilidadSerializer(request.user).data)
 
    def patch(self, request):
        serializer = DisponibilidadSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
 
 
class AreasTrabajoView(APIView):
    """Ver/definir las categorias en las que trabaja el proveedor."""
    permission_classes = [IsAuthenticated, IsProviderRole]
 
    def get(self, request):
        categorias = request.user.areas_trabajo.values('id_categoria', 'nombre')
        return Response(list(categorias))
 
    def put(self, request):
        serializer = AreasTrabajoSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        categorias = request.user.areas_trabajo.values('id_categoria', 'nombre')
        return Response(list(categorias))
 
 
class ResumenGananciasView(RetrieveAPIView):
    """Resumen de ganancias del proveedor logueado."""
    permission_classes = [IsAuthenticated, IsProviderRole]
    serializer_class = ResumenGananciasSerializer
 
    def get_object(self):
        return get_object_or_404(
            VistaResumenGanancias, proveedor_id=self.request.user.id_usuario
        )
 
 
class TrabajosAplicadosView(ListAPIView):
    """
    Postulaciones hechas por el proveedor logueado, en todos los estados.
    Filtros opcionales via query params:
      ?estado_id=1      (pendiente/contraoferta/rechazado/aceptado/finalizado)
      ?categoria_id=1   (una de las categorias del proveedor)
    """
    permission_classes = [IsAuthenticated, IsProviderRole]
    serializer_class = TrabajoAplicadoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['estado_id', 'categoria_id']

    def get_queryset(self):
        return VistaTrabajosAplicados.objects.filter(
            proveedor_id=self.request.user.id_usuario
        ).order_by('-id_postulacion')


class TrabajosAplicadosCardsView(TrabajosAplicadosView):
    """
    Mismo listado que /trabajos-aplicados/ (mismos filtros), pero con el
    shape reducido para las cards: categoria, estado, titulo, tiempo
    transcurrido, presupuesto y una sola foto.
    """
    serializer_class = TrabajoAplicadoCardSerializer



class TrabajosDisponiblesView(ListAPIView):
    """
    Trabajos disponibles para el proveedor logueado, paginados y filtrados
    por sus areas de trabajo. Filtros opcionales via query params:
      ?categoria_id=1        (una categoria especifica dentro de sus areas)
      ?precio_min=100
      ?precio_max=500
      ?page=2
      ?page_size=10          (max 50)
    """
    permission_classes = [IsAuthenticated, IsProviderRole]
    serializer_class = TrabajoDisponibleSerializer
    pagination_class = MisPublicacionesPagination

    def get_queryset(self):
        areas = self.request.user.areas_trabajo.values_list('id_categoria', flat=True)
        queryset = VistaTrabajosDisponibles.objects.filter(categoria_id__in=areas)
 
        categoria_id = self.request.query_params.get('categoria_id')
        if categoria_id:
            queryset = queryset.filter(categoria_id=categoria_id)
 
        precio_min = self.request.query_params.get('precio_min')
        if precio_min:
            queryset = queryset.filter(precio_inicial__gte=precio_min)
 
        precio_max = self.request.query_params.get('precio_max')
        if precio_max:
            queryset = queryset.filter(precio_inicial__lte=precio_max)
 
        return queryset.order_by('-fecha')

class ProveedorCategoriasView(APIView):
    """Categorias (areas de trabajo) que ofrece un proveedor. Publico."""
    permission_classes = [AllowAny]
 
    def get(self, request, id_usuario):
        usuario = get_object_or_404(Usuario, pk=id_usuario)
        categorias = usuario.areas_trabajo.values('id_categoria', 'nombre')
        return Response(list(categorias))
 
 
class UltimasResenasView(ListAPIView):
    """Ultimas 3 resenas recibidas por un usuario (cliente o proveedor). Publico."""
    permission_classes = [AllowAny]
    serializer_class = UltimaResenaSerializer
 
    def get_queryset(self):
        id_usuario = self.kwargs['id_usuario']
        return VistaUltimaResena.objects.raw(
            'SELECT * FROM ultimas_resenas(%s)', [str(id_usuario)]
        )


class NotificacionListView(ListAPIView):
    """Notificaciones del usuario autenticado, mas recientes primero.
    Filtro opcional: ?leido=true o ?leido=false
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificacionSerializer
 
    def get_queryset(self):
        queryset = Notificacion.objects.filter(usuario=self.request.user).order_by('-fecha')
        leido = self.request.query_params.get('leido')
        if leido is not None:
            queryset = queryset.filter(leido=leido.lower() == 'true')
        return queryset
 
 
class NotificacionMarkReadView(APIView):
    """Marca UNA notificacion como leida. Solo el dueno."""
    permission_classes = [IsAuthenticated]
 
    def patch(self, request, id_notificacion):
        notificacion = get_object_or_404(Notificacion, pk=id_notificacion)
        if notificacion.usuario_id != request.user.id_usuario:
            raise PermissionDenied('No puedes modificar una notificación que no es tuya.')
        notificacion.leido = True
        notificacion.save(update_fields=['leido'])
        return Response(NotificacionSerializer(notificacion).data)
 
 
class NotificacionMarkAllReadView(APIView):
    """Marca TODAS las notificaciones del usuario autenticado como leidas."""
    permission_classes = [IsAuthenticated]
 
    def patch(self, request):
        actualizadas = Notificacion.objects.filter(
            usuario=request.user, leido=False
        ).update(leido=True)
        return Response({'detail': f'{actualizadas} notificaciones marcadas como leídas.'})


class PortafolioListView(ListAPIView):
    """Portafolio publico de un proveedor."""
    permission_classes = [AllowAny]
    serializer_class = PortafolioSerializer
 
    def get_queryset(self):
        id_usuario = self.kwargs['id_usuario']
        return PortafolioProveedor.objects.filter(proveedor_id=id_usuario).order_by('-fecha')
 
 
class PortafolioCreateView(APIView):
    """Agrega un trabajo al portafolio. Solo el proveedor logueado, para si mismo."""
    permission_classes = [IsAuthenticated, IsProviderRole]
 
    def post(self, request):
        serializer = CreatePortafolioSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(PortafolioSerializer(item).data, status=status.HTTP_201_CREATED)
 
 
class PortafolioDeleteView(APIView):
    """Elimina un item del portafolio. Solo el dueno."""
    permission_classes = [IsAuthenticated, IsProviderRole]
 
    def delete(self, request, id_portafolio):
        item = get_object_or_404(PortafolioProveedor, pk=id_portafolio)
        if item.proveedor_id != request.user.id_usuario:
            raise PermissionDenied('No puedes eliminar un portafolio que no es tuyo.')
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)