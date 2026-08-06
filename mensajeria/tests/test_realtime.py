"""Tests de la capa Realtime (mensajeria.realtime).

Verifica el flujo real de publish_event → _broadcast_async: crear cliente,
suscribirse al canal conversacion-<id>, enviar el broadcast y liberar el
canal (sin depender de una instancia de Supabase).
"""

import asyncio
from unittest.mock import patch

from django.test import SimpleTestCase

from mensajeria import realtime


class FakeChannel:
    def __init__(self, name, params=None):
        self.name = name
        self.params = params
        self.subscribed = False
        self.sent = None

    async def subscribe(self):
        self.subscribed = True

    def send_broadcast(self, event, data):
        self.sent = (event, data)


class FakeClient:
    def __init__(self):
        self.channels = []
        self.removed = None

    def channel(self, name, params=None):
        ch = FakeChannel(name, params)
        self.channels.append(ch)
        return ch

    async def remove_channel(self, channel):
        self.removed = channel


class BroadcastAsyncTests(SimpleTestCase):
    """_broadcast_async: subscribe, broadcast y cleanup sobre el canal."""

    def test_broadcast_async_flow(self):
        client = FakeClient()

        async def fake_create_async_client(url, key):
            return client

        with patch("supabase.create_async_client", fake_create_async_client):
            asyncio.run(realtime._broadcast_async("conversacion-42", "new_message", {"text": "hola"}))

        self.assertEqual(len(client.channels), 1)
        channel = client.channels[0]
        self.assertEqual(channel.name, "conversacion-42")
        self.assertEqual(channel.params, {"config": {"private": True}}, "canal debe ser privado")
        self.assertTrue(channel.subscribed, "debe suscribirse al canal")
        self.assertEqual(channel.sent, ("new_message", {"text": "hola"}))
        self.assertIs(client.removed, channel, "debe liberar el canal al terminar")


class PublishEventTests(SimpleTestCase):
    """publish_event: corre en hilo daemon y usa el canal conversacion-<id>."""

    def test_publish_event_target_and_channel(self):
        calls = []

        async def fake_broadcast(channel_name, event, payload):
            calls.append((channel_name, event, payload))

        class FakeThread:
            def __init__(self, target, daemon):
                self.target = target
                self.daemon = daemon

            def start(self):
                self.target()

        with (
            patch.object(realtime, "_broadcast_async", side_effect=fake_broadcast),
            patch("threading.Thread", FakeThread),
        ):
            realtime.publish_event(7, "typing_start", {"user_id": "u1"})

        self.assertEqual(
            calls, [("conversacion-7", "typing_start", {"user_id": "u1"})]
        )

    def test_publish_event_survives_failures(self):
        """Un fallo del broadcast no propaga (best-effort)."""
        async def failing(channel_name, event, payload):
            raise ConnectionError("supabase caido")

        class FakeThread:
            def __init__(self, target, daemon):
                self.target = target
                self.daemon = daemon

            def start(self):
                self.target()

        with (
            patch.object(realtime, "_broadcast_async", side_effect=failing),
            patch("threading.Thread", FakeThread),
        ):
            realtime.publish_event(1, "new_message", {})  # no debe lanzar
