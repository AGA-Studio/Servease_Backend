import json
import time
from types import SimpleNamespace

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Q

from mensajeria.models import Bloqueo, Conversacion, Mensaje
from mensajeria.serializers import MensajeSerializer


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time chat messaging.

    - Client connects to ws://.../ws/mensajeria/<conversacion_id>/?token=<jwt>
    - On connect: validates user is a conversation participant, joins group
    - On receive: persists message to DB, broadcasts to group
    - On disconnect: leaves group
    - Supports: new_message, typing_start, typing_stop
    """

    # Max WebSocket messages per second before rate-limiting
    WS_RATE_LIMIT = 10

    async def connect(self):
        self.conversacion_id = self.scope["url_route"]["kwargs"]["conversacion_id"]
        self.room_group_name = f"chat_{self.conversacion_id}"

        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        # Check if user is blocked in this conversation
        is_blocked = await self._check_blocked(user, self.conversacion_id)
        if is_blocked:
            await self.close(code=4004)
            return

        is_participant = await self._check_participant(user, self.conversacion_id)
        if not is_participant:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        action = data.get("action", "new_message")

        # Rate limiting for new_message actions
        if action == "new_message":
            now = time.time()
            if not hasattr(self, "_last_msg_times"):
                self._last_msg_times = []
            # Keep only messages within the last second
            self._last_msg_times = [t for t in self._last_msg_times if now - t < 1.0]
            if len(self._last_msg_times) >= self.WS_RATE_LIMIT:
                await self.send(
                    text_data=json.dumps({"error": "rate_limit", "detail": "Demasiados mensajes. Intenta de nuevo."})
                )
                return
            self._last_msg_times.append(now)

        if action == "new_message":
            await self._handle_new_message(data)
        elif action == "typing_start":
            await self._handle_typing_start(data)
        elif action == "typing_stop":
            await self._handle_typing_stop(data)

    async def _handle_new_message(self, data):
        user = self.scope["user"]
        contenido = data.get("contenido", "").strip()

        if not contenido and not data.get("archivo"):
            return

        mensaje, err = await self._save_message(
            user, self.conversacion_id, contenido, data.get("reply_to")
        )
        if err == "not_found":
            await self.send(
                text_data=json.dumps({"error": "not_found", "detail": "Conversacion no encontrada."})
            )
            return
        if err == "archived":
            await self.send(
                text_data=json.dumps({"error": "archived", "detail": "La conversacion esta archivada."})
            )
            return
        if err == "blocked":
            await self.send(
                text_data=json.dumps({"error": "blocked", "detail": "No puedes enviar mensajes en esta conversacion."})
            )
            return
        if err:
            await self.send(
                text_data=json.dumps({"error": "server_error", "detail": "Error al enviar el mensaje."})
            )
            return

        # Serialize with sender's context for per-receiver sender computation
        serialized = MensajeSerializer(
            mensaje, context={"request": SimpleNamespace(user=user)}
        ).data
        serialized["emisor_id"] = str(user.id_usuario)

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "chat_message", "data": serialized},
        )

    async def _handle_typing_start(self, data):
        """Broadcast typing_start to other participant."""
        user = self.scope["user"]
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing_indicator",
                "action": "typing_start",
                "user_id": str(user.id_usuario),
                "user_name": f"{user.nombre} {user.apellido_pa}",
            },
        )

    async def _handle_typing_stop(self, data):
        """Broadcast typing_stop to other participant."""
        user = self.scope["user"]
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing_indicator",
                "action": "typing_stop",
                "user_id": str(user.id_usuario),
            },
        )

    async def chat_message(self, event):
        """Handler for messages received from the group.
        Recomputes sender per-receiver based on their user identity."""
        data = dict(event["data"])
        user = self.scope.get("user")
        if user and user.is_authenticated and "emisor_id" in data:
            data["sender"] = (
                "user" if str(data["emisor_id"]) == str(user.id_usuario) else "other"
            )
        await self.send(text_data=json.dumps(data))

    async def typing_indicator(self, event):
        """Handler for typing start/stop events."""
        # Don't send back to sender
        user = self.scope.get("user")
        if (
            user
            and user.is_authenticated
            and event.get("user_id") == str(user.id_usuario)
        ):
            return
        await self.send(
            text_data=json.dumps(
                {
                    "action": event["action"],
                    "user_id": event["user_id"],
                    "user_name": event.get("user_name", ""),
                }
            )
        )

    async def read_receipt(self, event):
        """Handler for read receipt broadcast."""
        user = self.scope.get("user")
        if (
            user
            and user.is_authenticated
            and event.get("reader_id") == str(user.id_usuario)
        ):
            return
        await self.send(
            text_data=json.dumps(
                {
                    "action": "read_receipt",
                    "conversacion_id": event["conversacion_id"],
                    "reader_id": event["reader_id"],
                    "count": event["count"],
                }
            )
        )

    @sync_to_async(thread_sensitive=False)
    def _check_participant(self, user, conversacion_id):
        try:
            conv = Conversacion.objects.get(pk=conversacion_id)
        except Conversacion.DoesNotExist:
            return False
        return str(conv.cliente_id) == str(user.id_usuario) or str(
            conv.proveedor_id
        ) == str(user.id_usuario)

    @sync_to_async(thread_sensitive=False)
    def _check_blocked(self, user, conversacion_id):
        """Check if user is blocked in this conversation."""
        try:
            conv = Conversacion.objects.get(pk=conversacion_id)
        except Conversacion.DoesNotExist:
            return True  # Treat non-existent as blocked

        return Bloqueo.objects.filter(
            Q(usuario_bloqueador=conv.cliente, usuario_bloqueado=user)
            | Q(usuario_bloqueador=conv.proveedor, usuario_bloqueado=user)
        ).exists()

    @sync_to_async(thread_sensitive=False)
    def _save_message(self, user, conversacion_id, contenido, reply_to_id=None):
        """Persist message - trigger handles: unread_count, preview, fecha, editado, estado_entrega, tipo_mensaje."""
        from django.db.utils import DatabaseError

        try:
            conv = Conversacion.objects.get(pk=conversacion_id)
        except Conversacion.DoesNotExist:
            return None, "not_found"

        reply_to = None
        if reply_to_id:
            try:
                reply_to = Mensaje.objects.get(
                    id_mensaje=reply_to_id, conversacion=conv
                )
            except Mensaje.DoesNotExist:
                pass

        try:
            mensaje = Mensaje.objects.create(
                conversacion=conv,
                emisor=user,
                contenido=contenido,
                reply_to=reply_to,
            )
        except DatabaseError as e:
            if "MSG_IN_ARCHIVED" in str(e):
                return None, "archived"
            if "MSG_SENDER_BLOCKED" in str(e):
                return None, "blocked"
            return None, "db_error"

        return mensaje, None
