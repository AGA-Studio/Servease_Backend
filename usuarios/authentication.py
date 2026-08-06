import jwt
from jwt import PyJWKClient
from django.conf import settings
from django.db import IntegrityError
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import Usuario

_jwks_client = PyJWKClient(settings.SUPABASE_JWKS_URL)


class SupabaseAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ')[1]

        try:
            signing_key = _jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=['ES256', 'RS256'],
                audience='authenticated',
                issuer=f'{settings.SUPABASE_URL}/auth/v1',
            )
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Token inválido o expirado')

        try:
            usuario = Usuario.objects.get(pk=payload.get('sub'))
        except Usuario.DoesNotExist:
            usuario = self._provision_from_oauth(payload)

        if not usuario.estado:
            raise AuthenticationFailed(
                'Tu cuenta no ha sido confirmada. Revisa tu correo.'
            )

        return (usuario, token)

    def _provision_from_oauth(self, payload):
        """Crea la fila Usuario en el primer login vía OAuth (Google), ya
        que ese flujo nunca pasa por SignupView. Solo aplica a proveedores
        externos: un usuario sin fila y sin OAuth es un id_usuario ajeno al
        sistema."""
        app_metadata = payload.get('app_metadata') or {}
        if app_metadata.get('provider') != 'google':
            raise AuthenticationFailed('Usuario no encontrado en el sistema')

        user_metadata = payload.get('user_metadata') or {}
        nombre = user_metadata.get('given_name') or ''
        family_name = user_metadata.get('family_name') or ''
        apellido_pa, _, apellido_ma = family_name.partition(' ')

        if not nombre and not apellido_pa:
            # Google no siempre manda given_name/family_name por separado;
            # aproximamos con las últimas 1-2 palabras del nombre completo.
            full_name = user_metadata.get('full_name') or user_metadata.get('name') or ''
            words = full_name.split()
            if len(words) >= 3:
                nombre = ' '.join(words[:-2])
                apellido_pa, apellido_ma = words[-2], words[-1]
            elif len(words) == 2:
                nombre, apellido_pa = words
            elif len(words) == 1:
                nombre = words[0]

        try:
            return Usuario.objects.create(
                id_usuario=payload['sub'],
                nombre=nombre,
                apellido_pa=apellido_pa,
                apellido_ma=apellido_ma or None,
                correo=payload.get('email') or '',
                rol_id=1,
                estado=True,
                url_foto_perfil=user_metadata.get('picture')
                or user_metadata.get('avatar_url'),
            )
        except IntegrityError:
            try:
                return Usuario.objects.get(pk=payload['sub'])
            except Usuario.DoesNotExist:
                raise AuthenticationFailed(
                    'Ya existe una cuenta con este correo. Inicia sesión con tu contraseña.'
                )


# drf-spectacular: expone SupabaseAuthentication como esquema bearerAuth
# para que Swagger UI muestre el botón "Authorize".
from drf_spectacular.extensions import OpenApiAuthenticationExtension  # noqa: E402


class SupabaseBearerScheme(OpenApiAuthenticationExtension):
    target_class = "usuarios.authentication.SupabaseAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
