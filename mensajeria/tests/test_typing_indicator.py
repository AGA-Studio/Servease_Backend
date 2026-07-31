"""Tests for typing indicator WebSocket events."""

import uuid

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

from mensajeria.consumers import ChatConsumer
from mensajeria.models import Conversacion
from usuarios.models import Rol, Usuario


class TypingIndicatorTests(TransactionTestCase):
    """Tests for typing_start / typing_stop WebSocket events."""

    def setUp(self):
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

    async def test_typing_start_broadcasts_to_other_participant(self):
        """typing_start event broadcasts to other participant in conversation."""
        comm_cliente, connected = await self.get_communicator(self.cliente)
        self.assertTrue(connected)

        comm_proveedor, connected2 = await self.get_communicator(self.proveedor)
        self.assertTrue(connected2)

        # Cliente sends typing_start
        await comm_cliente.send_json_to(
            {
                "action": "typing_start",
            }
        )

        # Proveedor should receive typing indicator
        msg = await comm_proveedor.receive_json_from(timeout=5)
        self.assertEqual(msg["action"], "typing_start")
        self.assertEqual(msg["user_id"], str(self.cliente.id_usuario))
        self.assertEqual(msg["user_name"], "Cliente Test")

    async def test_typing_stop_broadcasts_to_other_participant(self):
        """typing_stop event broadcasts to other participant."""
        comm_cliente, connected = await self.get_communicator(self.cliente)
        self.assertTrue(connected)

        comm_proveedor, connected2 = await self.get_communicator(self.proveedor)
        self.assertTrue(connected2)

        # Cliente sends typing_stop
        await comm_cliente.send_json_to(
            {
                "action": "typing_stop",
            }
        )

        # Proveedor should receive typing_stop
        msg = await comm_proveedor.receive_json_from(timeout=5)
        self.assertEqual(msg["action"], "typing_stop")
        self.assertEqual(msg["user_id"], str(self.cliente.id_usuario))

    async def test_typing_start_only_sent_to_other_participant(self):
        """typing_start is NOT sent back to sender."""
        comm_cliente, connected = await self.get_communicator(self.cliente)
        self.assertTrue(connected)

        comm_proveedor, connected2 = await self.get_communicator(self.proveedor)
        self.assertTrue(connected2)

        await comm_cliente.send_json_to({"action": "typing_start"})

        # Proveedor receives it
        msg = await comm_proveedor.receive_json_from(timeout=5)
        self.assertEqual(msg["action"], "typing_start")

        # Cliente should NOT receive it back
        import asyncio

        with self.assertRaises(asyncio.TimeoutError):
            await comm_cliente.receive_json_from(timeout=1)

    async def test_typing_stop_only_sent_to_other_participant(self):
        """typing_stop is NOT sent back to sender."""
        comm_cliente, connected = await self.get_communicator(self.cliente)
        self.assertTrue(connected)

        comm_proveedor, connected2 = await self.get_communicator(self.proveedor)
        self.assertTrue(connected2)

        await comm_cliente.send_json_to({"action": "typing_stop"})

        msg = await comm_proveedor.receive_json_from(timeout=5)
        self.assertEqual(msg["action"], "typing_stop")

        import asyncio

        with self.assertRaises(asyncio.TimeoutError):
            await comm_cliente.receive_json_from(timeout=1)

    async def test_typing_events_ignored_for_non_participant(self):
        """Non-participant cannot send typing events (connection rejected)."""
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
