"""
ASGI config for Servease_Backend project.

Expone el callable ``application``. Sin Django Channels: el tiempo real
se maneja vía Supabase Realtime, el servidor solo sirve HTTP.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Servease_Backend.settings")

application = get_asgi_application()
