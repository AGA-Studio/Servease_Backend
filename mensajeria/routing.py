from django.urls import re_path

from mensajeria.consumers import ChatConsumer

websocket_urlpatterns = [
    re_path(
        r"ws/mensajeria/(?P<conversacion_id>\d+)/$",
        ChatConsumer.as_asgi(),
        name="ws-mensajeria-chat",
    ),
]
