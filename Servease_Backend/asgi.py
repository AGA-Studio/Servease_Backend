"""
ASGI config for Servease_Backend project.

It exposes the ASGI callable as a module-level variable named ``application``.
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Servease_Backend.settings")

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing consumers and auth middleware.
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack

from mensajeria.auth_ws import JWTAuthMiddleware
from mensajeria.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddleware(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
