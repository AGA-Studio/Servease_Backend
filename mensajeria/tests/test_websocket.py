"""Tests for WebSocket consumer and JWT auth middleware."""

import uuid
from unittest.mock import MagicMock, patch

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

from mensajeria.consumers import ChatConsumer
from mensajeria.models import Conversacion, Mensaje
from usuarios.models import Rol, Usuario


class JWTAuthMiddlewareTests(TransactionTestCase):
    """Tests for WebSocket JWT authentication middleware logic paths."""

    async def _make_scope(self, query_string=b""):
        return {
            "type": "websocket",
            "query_string": query_string,
            "path": "/ws/test/",
        }

    async def _run_middleware(self, scope, mock_inner=None):
        """Run JWTAuthMiddleware.__call__ with a mock inner app and return (sent, inner_called)."""
        from mensajeria.auth_ws import JWTAuthMiddleware

        inner_called = False

        async def default_inner(s, r, send):
            nonlocal inner_called
            inner_called = True

        inner = mock_inner or default_inner
        app = JWTAuthMiddleware(inner)
        sent = []

        async def mock_send(msg):
            sent.append(msg)

        # Events in ASGI consumer lifecycle order:
        # 1. websocket.connect  → triggers connect() → close() for denier
        # 2. websocket.disconnect → triggers disconnect() → StopConsumer
        step = 0

        async def mock_receive():
            nonlocal step
            step += 1
            if step == 1:
                return {"type": "websocket.connect"}
            return {"type": "websocket.disconnect", "code": 1000}

        await app(scope, mock_receive, mock_send)
        return sent, inner_called

    async def test_missing_token_returns_close(self):
        """No token in query string sends websocket.close."""
        sent, inner_called = await self._run_middleware(await self._make_scope(b""))
        close_msgs = [m for m in sent if m.get("type") == "websocket.close"]
        self.assertTrue(close_msgs, msg=f"Expected close, got: {sent}")
        self.assertFalse(
            inner_called,
            msg="Inner ASGI app should not be called when token is missing",
        )

    @patch("mensajeria.auth_ws.jwt.decode")
    async def test_invalid_token_returns_close(self, mock_decode):
        """Invalid JWT sends websocket.close."""
        mock_decode.side_effect = Exception("invalid token")
        sent, inner_called = await self._run_middleware(
            await self._make_scope(b"token=fake.jwt.tok")
        )
        close_msgs = [m for m in sent if m.get("type") == "websocket.close"]
        self.assertTrue(close_msgs, msg=f"Expected close on invalid token, got: {sent}")
        self.assertFalse(
            inner_called, msg="Inner should not be called on invalid token"
        )

    @patch("jwt.PyJWKClient")
    async def test_network_error_returns_close(self, mock_jwks_client):
        """Network error during JWKS fetch sends websocket.close."""
        client_instance = MagicMock()
        mock_jwks_client.return_value = client_instance
        client_instance.get_signing_key_from_jwt.side_effect = ConnectionError(
            "JWKS dead"
        )

        sent, inner_called = await self._run_middleware(
            await self._make_scope(b"token=fake.jwt.tok")
        )
        close_msgs = [m for m in sent if m.get("type") == "websocket.close"]
        self.assertTrue(close_msgs, msg=f"Expected close on network error, got: {sent}")
        self.assertFalse(
            inner_called, msg="Inner should not be called on network error"
        )


class ChatConsumerTests(TransactionTestCase):
    """Tests for ChatConsumer WebSocket endpoint."""

    def setUp(self):
        """Create test users and conversation with unique UUIDs."""
        super().setUp()
        self.rol_cliente = Rol.objects.create(id_rol=1, nombre="Cliente")
        self.rol_proveedor = Rol.objects.create(id_rol=2, nombre="Proveedor")
        self.cliente_uuid = uuid.uuid4()
        self.proveedor_uuid = uuid.uuid4()
        self.cliente = Usuario.objects.create(
            id_usuario=self.cliente_uuid,
            nombre="Cliente",
            apellido_pa="Test",
            correo=f"__VG_WS_CLIENT_{self.cliente_uuid}__",
            rol=self.rol_cliente,
        )
        self.proveedor = Usuario.objects.create(
            id_usuario=self.proveedor_uuid,
            nombre="Proveedor",
            apellido_pa="Test",
            correo=f"__VG_WS_PROV_{self.proveedor_uuid}__",
            rol=self.rol_proveedor,
        )
        self.conv = Conversacion.objects.create(
            cliente=self.cliente,
            proveedor=self.proveedor,
        )

    async def get_communicator(self, user):
        """Create a WebsocketCommunicator connected as the given user."""
        app = ChatConsumer.as_asgi()
        communicator = WebsocketCommunicator(
            app,
            f"/ws/mensajeria/{self.conv.id_conversacion}/",
        )
        communicator.scope["user"] = user
        communicator.scope["url_route"] = {
            "kwargs": {"conversacion_id": str(self.conv.id_conversacion)},
        }
        connected, _ = await communicator.connect()
        return communicator, connected

    async def test_connect_unauthenticated(self):
        """Connection without user is rejected with 4001."""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            "/ws/mensajeria/1/",
        )
        anon = MagicMock()
        anon.is_authenticated = False
        communicator.scope["user"] = anon
        communicator.scope["url_route"] = {"kwargs": {"conversacion_id": "1"}}
        connected, _ = await communicator.connect()
        self.assertFalse(connected)

    async def test_connect_non_participant(self):
        """Connection from non-participant is rejected with 4003."""
        outsider_uuid = uuid.uuid4()
        outsider = await sync_to_async(Usuario.objects.create)(
            id_usuario=outsider_uuid,
            nombre="Outsider",
            apellido_pa="Test",
            correo=f"__VG_WS_OUT_{outsider_uuid}__",
            rol=self.rol_cliente,
        )
        _communicator, connected = await self.get_communicator(outsider)
        self.assertFalse(connected)

    async def test_connect_participant(self):
        """Participant can connect successfully."""
        communicator, connected = await self.get_communicator(self.cliente)
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_send_message(self):
        """Sending a new_message persists and broadcasts."""
        communicator, connected = await self.get_communicator(self.cliente)
        self.assertTrue(connected)

        await communicator.send_json_to(
            {
                "action": "new_message",
                "contenido": "Hola desde WS!",
            }
        )

        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response["text"], "Hola desde WS!")
        self.assertEqual(response["sender"], "user")
        self.assertEqual(response["senderName"], "Cliente Test")

        msg_count = await sync_to_async(Mensaje.objects.count)()
        self.assertEqual(msg_count, 1)
        await communicator.disconnect()

    async def test_send_message_broadcasts_to_group(self):
        """Both participants in the group receive the message with correct sender."""
        comm_cliente, connected = await self.get_communicator(self.cliente)
        self.assertTrue(connected)

        comm_proveedor, connected2 = await self.get_communicator(self.proveedor)
        self.assertTrue(connected2)

        await comm_cliente.send_json_to(
            {
                "action": "new_message",
                "contenido": "Broadcast test!",
            }
        )

        msg1 = await comm_cliente.receive_json_from(timeout=5)
        msg2 = await comm_proveedor.receive_json_from(timeout=5)

        self.assertEqual(msg1["text"], "Broadcast test!")
        self.assertEqual(msg2["text"], "Broadcast test!")
        self.assertEqual(msg1["sender"], "user", "Sender should see 'user'")
        self.assertEqual(msg2["sender"], "other", "Receiver should see 'other'")

        await comm_cliente.disconnect()
        await comm_proveedor.disconnect()

    async def test_empty_message_ignored(self):
        """Empty or whitespace-only message is silently ignored."""
        communicator, connected = await self.get_communicator(self.cliente)
        self.assertTrue(connected)

        await communicator.send_json_to(
            {
                "action": "new_message",
                "contenido": "   ",
            }
        )

        import asyncio

        with self.assertRaises(asyncio.TimeoutError):
            await communicator.receive_json_from(timeout=2)

        msg_count = await sync_to_async(Mensaje.objects.count)()
        self.assertEqual(msg_count, 0)

    async def test_invalid_json_ignored(self):
        """Non-JSON text data is silently ignored."""
        communicator, connected = await self.get_communicator(self.cliente)
        self.assertTrue(connected)

        await communicator.send_to(text_data="not json at all")

        import asyncio

        with self.assertRaises(asyncio.TimeoutError):
            await communicator.receive_json_from(timeout=2)

    async def test_rate_limiting(self):
        """Rate limit blocks excessive messages in the window."""
        with patch.object(ChatConsumer, "WS_RATE_LIMIT", 3):
            communicator, connected = await self.get_communicator(self.cliente)
            self.assertTrue(connected)

            for i in range(3):
                await communicator.send_json_to(
                    {
                        "action": "new_message",
                        "contenido": f"msg {i}",
                    }
                )
                msg = await communicator.receive_json_from(timeout=5)
                self.assertEqual(msg["text"], f"msg {i}")

            # 4th message should be rate-limited
            await communicator.send_json_to(
                {
                    "action": "new_message",
                    "contenido": "too many",
                }
            )
            error = await communicator.receive_json_from(timeout=5)
            self.assertEqual(error["error"], "rate_limit")

            await communicator.disconnect()

    async def test_blocked_user_cannot_connect_ws(self):
        """Blocked user cannot connect to WebSocket (close 4004)."""
        from mensajeria.models import Bloqueo

        await sync_to_async(Bloqueo.objects.create)(
            usuario_bloqueador=self.cliente,
            usuario_bloqueado=self.proveedor,
            motivo="Spam",
        )
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/mensajeria/{self.conv.id_conversacion}/",
        )
        communicator.scope["user"] = self.proveedor
        communicator.scope["url_route"] = {
            "kwargs": {"conversacion_id": str(self.conv.id_conversacion)}
        }
        connected, _ = await communicator.connect()
        self.assertFalse(connected)

    async def test_ws_delivery_updates_to_recibido(self):
        """Connecting as recipient marks pending messages from the other user as 'recibido'."""
        msg = await sync_to_async(Mensaje.objects.create)(
            conversacion=self.conv,
            emisor=self.cliente,
            contenido="Hola",
        )
        self.assertEqual(msg.estado_entrega, "enviado")

        communicator, connected = await self.get_communicator(self.proveedor)
        self.assertTrue(connected)

        await sync_to_async(msg.refresh_from_db)()
        self.assertEqual(msg.estado_entrega, "recibido")
        await communicator.disconnect()
