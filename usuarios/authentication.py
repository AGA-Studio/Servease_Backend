import jwt
from jwt import PyJWKClient
from django.conf import settings
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
            raise AuthenticationFailed('Usuario no encontrado en el sistema')

        return (usuario, token)