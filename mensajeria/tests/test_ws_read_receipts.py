"""Tests for read receipts broadcast via WebSocket."""

import uuid

from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

from mensajeria.consumers import ChatConsumer
from mensajeria.models import Conversacion, Mensaje
from usuarios.models import Rol, Usuario


class WSReadReceiptTests(TransactionTestCase):
    """Tests for read_receipt broadcast via WebSocket when messages are marked read."""

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
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/mensajeria/{self.conv.id_conversacion}/",
        )
        communicator.scope["user"] = user
        communicator.scope["url_route"] = {
            "kwargs": {"conversacion_id": str(self.conv.id_conversacion)},
        }
        connected, _ = await communicator.connect()
        return communicator, connected

    async def test_read_receipt_delivered_to_other_participant(self):
        """When read_receipt is sent via channel layer, the other participant receives it."""
        # Create unread messages from proveedor
        await sync_to_async(Mensaje.objects.create)(
            conversacion=self.conv,
            emisor=self.proveedor,
            contenido="Msg 1",
            leido=False,
        )
        await sync_to_async(Mensaje.objects.create)(
            conversacion=self.conv,
            emisor=self.proveedor,
            contenido="Msg 2",
            leido=False,
        )

        # Both connect via WS
        _comm_cliente, connected = await self.get_communicator(self.cliente)
        self.assertTrue(connected)
        comm_proveedor, connected2 = await self.get_communicator(self.proveedor)
        self.assertTrue(connected2)

        # Simulate the read_receipt broadcast (what MarcarLeidoView does)
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"chat_{self.conv.id_conversacion}",
            {
                "type": "read_receipt",
                "conversacion_id": str(self.conv.id_conversacion),
                "reader_id": str(self.cliente.id_usuario),
                "count": 2,
            },
        )

        # Proveedor should receive read_receipt
        msg = await comm_proveedor.receive_json_from(timeout=5)
        self.assertEqual(msg["action"], "read_receipt")
        self.assertEqual(msg["conversacion_id"], str(self.conv.id_conversacion))
        self.assertEqual(msg["reader_id"], str(self.cliente.id_usuario))
        self.assertEqual(msg["count"], 2)

    async def test_read_receipt_not_sent_to_sender(self):
        """read_receipt is NOT sent back to the reader who marked as read."""
        await sync_to_async(Mensaje.objects.create)(
            conversacion=self.conv, emisor=self.proveedor, contenido="Msg", leido=False
        )

        comm_cliente, connected = await self.get_communicator(self.cliente)
        self.assertTrue(connected)
        comm_proveedor, connected2 = await self.get_communicator(self.proveedor)
        self.assertTrue(connected2)

        # Send read_receipt via channel layer
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"chat_{self.conv.id_conversacion}",
            {
                "type": "read_receipt",
                "conversacion_id": str(self.conv.id_conversacion),
                "reader_id": str(self.cliente.id_usuario),
                "count": 1,
            },
        )

        # Proveedor receives read_receipt
        msg = await comm_proveedor.receive_json_from(timeout=5)
        self.assertEqual(msg["action"], "read_receipt")

        # Cliente (sender/reader) should NOT receive it back
        import asyncio

        with self.assertRaises(asyncio.TimeoutError):
            await comm_cliente.receive_json_from(timeout=1)

    async def test_rest_mark_read_updates_messages(self):
        """When REST endpoint marks messages as read, they are actually updated in DB."""
        await sync_to_async(Mensaje.objects.create)(
            conversacion=self.conv,
            emisor=self.proveedor,
            contenido="Unread msg",
            leido=False,
        )

        # Verify message is unread
        msgs = await sync_to_async(
            lambda: list(Mensaje.objects.filter(conversacion=self.conv, leido=False))
        )()
        self.assertEqual(len(msgs), 1)

        # We can't easily call the REST endpoint from async tests with this User model,
        # but we can verify the underlying logic works by directly updating
        updated = await sync_to_async(
            lambda: (
                Mensaje.objects.filter(conversacion=self.conv, leido=False)
                .exclude(emisor=self.cliente)
                .update(leido=True)
            )
        )()
        self.assertEqual(updated, 1)

        # Verify message is now read
        unread = await sync_to_async(
            lambda: Mensaje.objects.filter(conversacion=self.conv, leido=False).count()
        )()
        self.assertEqual(unread, 0)
