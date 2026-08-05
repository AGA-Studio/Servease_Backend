"""Tests de mensajería REST + publicación de eventos Realtime.

Reemplaza los tests de WebSocket/Channels: la capa en vivo ahora es
Supabase Realtime vía `publish_event` (fire-and-forget), así que estos
tests verifican que las vistas REST persisten y publican el evento correcto
sobre el canal de la conversación.
"""

import uuid
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from mensajeria.models import Conversacion, Mensaje
from usuarios.models import Rol, Usuario


class MensajeriaRealtimeEventTests(TestCase):
    """POST de mensaje crea el mensaje y publica new_message vía publish_event."""

    def setUp(self):
        self.rol_cliente = Rol.objects.create(id_rol=1, nombre="Cliente")
        self.rol_proveedor = Rol.objects.create(id_rol=2, nombre="Proveedor")
        self.cliente = Usuario.objects.create(
            id_usuario=uuid.uuid4(),
            nombre="Cliente",
            apellido_pa="Test",
            correo=f"__VG_RT_CLIENT_{uuid.uuid4()}__",
            rol=self.rol_cliente,
        )
        self.proveedor = Usuario.objects.create(
            id_usuario=uuid.uuid4(),
            nombre="Proveedor",
            apellido_pa="Test",
            correo=f"__VG_RT_PROV_{uuid.uuid4()}__",
            rol=self.rol_proveedor,
        )
        self.conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )
        self.api_client = APIClient()

    def _url_mensajes(self):
        return f"/api/mensajeria/conversaciones/{self.conv.id_conversacion}/mensajes/"

    # ─── Envío de mensaje ───

    def test_send_message_persists_and_publishes(self):
        """POST mensaje: persiste en BD y publica new_message."""
        self.api_client.force_authenticate(user=self.cliente)
        with patch("mensajeria.views.publish_event") as mock_pub:
            resp = self.api_client.post(
                self._url_mensajes(), {"contenido": "Hola desde REST!"}, format="json"
            )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["text"], "Hola desde REST!")
        self.assertEqual(Mensaje.objects.count(), 1)

        mock_pub.assert_called_once()
        conv_id, event, payload = mock_pub.call_args.args
        self.assertEqual(conv_id, self.conv.id_conversacion)
        self.assertEqual(event, "new_message")
        self.assertEqual(payload["text"], "Hola desde REST!")
        self.assertEqual(payload["emisor_id"], str(self.cliente.id_usuario))

    def test_message_payload_has_sender_info(self):
        """El payload incluye sender/senderName para que el frontend diferencie emisor."""
        self.api_client.force_authenticate(user=self.proveedor)
        with patch("mensajeria.views.publish_event") as mock_pub:
            self.api_client.post(
                self._url_mensajes(), {"contenido": "Otra prueba"}, format="json"
            )
        _, _, payload = mock_pub.call_args.args
        self.assertEqual(payload["senderName"], "Proveedor Test")

    def test_empty_message_rejected(self):
        """Mensaje vacío o solo espacios devuelve 400 (no publica nada)."""
        self.api_client.force_authenticate(user=self.cliente)
        with patch("mensajeria.views.publish_event") as mock_pub:
            resp = self.api_client.post(
                self._url_mensajes(), {"contenido": "   "}, format="json"
            )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Mensaje.objects.count(), 0)
        mock_pub.assert_not_called()

    def test_non_participant_cannot_post(self):
        """Un usuario fuera de la conversación recibe 403."""
        outsider = Usuario.objects.create(
            id_usuario=uuid.uuid4(),
            nombre="Outsider",
            apellido_pa="Test",
            correo=f"__VG_RT_OUT_{uuid.uuid4()}__",
            rol=self.rol_cliente,
        )
        self.api_client.force_authenticate(user=outsider)
        resp = self.api_client.post(
            self._url_mensajes(), {"contenido": "Intruso"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_rejected(self):
        """Sin autenticación: 403 (SupabaseAuthentication no emite WWW-Authenticate)."""
        resp = self.api_client.post(
            self._url_mensajes(), {"contenido": "Anon"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ─── Estado de entrega (equivalente al marcado del WS al conectar) ───

    def test_get_messages_marks_delivered(self):
        """GET de mensajes: los pendientes del otro pasan de 'enviado' a 'recibido'."""
        msg = Mensaje.objects.create(
            conversacion=self.conv, emisor=self.cliente, receptor=self.proveedor, contenido="Hola"
        )
        self.assertEqual(msg.estado_entrega, "enviado")

        self.api_client.force_authenticate(user=self.proveedor)
        resp = self.api_client.get(self._url_mensajes())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        msg.refresh_from_db()
        self.assertEqual(msg.estado_entrega, "recibido")

    # ─── Archivar conversación ───

    def test_archive_conversation(self):
        """DELETE archiva la conversación (estado ARCHIVADA=10)."""
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.delete(
            f"/api/mensajeria/conversaciones/{self.conv.id_conversacion}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.conv.refresh_from_db()
        from servicios.models.estado import ARCHIVADA

        self.assertEqual(self.conv.estado_id, ARCHIVADA)
