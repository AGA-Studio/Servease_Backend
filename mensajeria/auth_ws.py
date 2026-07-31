from urllib.parse import parse_qs

import jwt
from jwt import PyJWKClient
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from channels.security.websocket import WebsocketDenier
from django.conf import settings

from usuarios.models import Usuario


# Reuse one JWKS client across connections (same pattern as usuarios.authentication).
_jwks_client = PyJWKClient(settings.SUPABASE_JWKS_URL)


@database_sync_to_async
def get_user(payload):
    try:
        usuario = Usuario.objects.get(pk=payload.get("sub"))
    except Usuario.DoesNotExist:
        return None
    if not usuario.estado:
        return None
    return usuario


class JWTAuthMiddleware(BaseMiddleware):
    """
    ASGI middleware that extracts a JWT from the WebSocket query string
    (?token=<jwt>) and authenticates the user against Supabase JWKS.

    Uses the same token validation as the REST API (SupabaseAuthentication).
    """

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode("utf-8")
        params = parse_qs(query_string)
        token = params.get("token", [None])[0]

        if token is None:
            denier = WebsocketDenier()
            return await denier(scope, receive, send)

        payload = None
        try:
            signing_key = _jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
                issuer=f"{settings.SUPABASE_URL}/auth/v1",
            )
        except (jwt.PyJWKClientError, jwt.InvalidTokenError, ConnectionError):  # noqa: BLE001
            payload = None

        if payload is None:
            denier = WebsocketDenier()
            return await denier(scope, receive, send)

        user = await get_user(payload)
        if user is None:
            denier = WebsocketDenier()
            return await denier(scope, receive, send)

        scope["user"] = user
        return await super().__call__(scope, receive, send)
