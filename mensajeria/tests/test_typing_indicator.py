"""Tests del indicador de escritura (typing) vía REST + Supabase Realtime.

Reemplaza los tests de typing del WebSocket: ahora ConversacionTypingView
publica typing_start / typing_stop con publish_event sobre el canal.
"""

import uuid
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from mensajeria.models import Conversacion
from usuarios.models import Rol, Usuario


class TypingIndicatorTests(TestCase):
    """POST /typing/ publica typing_start / typing_stop."""

    def setUp(self):
        self.rol_cliente = Rol.objects.create(id_rol=1, nombre="Cliente")
        self.rol_proveedor = Rol.objects.create(id_rol=2, nombre="Proveedor")
        self.cliente = Usuario.objects.create(
            id_usuario=uuid.uuid4(),
            nombre="Cliente",
            apellido_pa="Test",
            correo=f"__VG_TP_CLIENT_{uuid.uuid4()}__",
            rol=self.rol_cliente,
        )
        self.proveedor = Usuario.objects.create(
            id_usuario=uuid.uuid4(),
            nombre="Proveedor",
            apellido_pa="Test",
            correo=f"__VG_TP_PROV_{uuid.uuid4()}__",
            rol=self.rol_proveedor,
        )
        self.conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )
        self.api_client = APIClient()
        self.url = f"/api/mensajeria/conversaciones/{self.conv.id_conversacion}/typing/"

    def _publish(self, user, action):
        self.api_client.force_authenticate(user=user)
        with patch("mensajeria.views.publish_event") as mock_pub:
            resp = self.api_client.post(self.url, {"action": action}, format="json")
        return resp, mock_pub

    def test_typing_start_publishes(self):
        """action=start publica typing_start con user_id y user_name."""
        resp, mock_pub = self._publish(self.cliente, "start")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        mock_pub.assert_called_once()
        conv_id, event, payload = mock_pub.call_args.args
        self.assertEqual(conv_id, self.conv.id_conversacion)
        self.assertEqual(event, "typing_start")
        self.assertEqual(payload["user_id"], str(self.cliente.id_usuario))
        self.assertEqual(payload["user_name"], "Cliente Test")

    def test_typing_stop_publishes(self):
        """action=stop publica typing_stop."""
        resp, mock_pub = self._publish(self.proveedor, "stop")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_pub.assert_called_once()
        _, event, payload = mock_pub.call_args.args
        self.assertEqual(event, "typing_stop")
        self.assertEqual(payload["user_id"], str(self.proveedor.id_usuario))

    def test_typing_defaults_to_start(self):
        """Sin action (o vacío) se publica typing_start."""
        self.api_client.force_authenticate(user=self.cliente)
        with patch("mensajeria.views.publish_event") as mock_pub:
            resp = self.api_client.post(self.url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_pub.assert_called_once()
        self.assertEqual(mock_pub.call_args.args[1], "typing_start")

    def test_invalid_action_rejected(self):
        """action inválido devuelve 400 y no publica nada."""
        resp, mock_pub = self._publish(self.cliente, "flame")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        mock_pub.assert_not_called()

    def test_non_participant_forbidden(self):
        """Un usuario fuera de la conversación no puede publicar typing (403)."""
        outsider = Usuario.objects.create(
            id_usuario=uuid.uuid4(),
            nombre="Outsider",
            apellido_pa="Test",
            correo=f"__VG_TP_OUT_{uuid.uuid4()}__",
            rol=self.rol_cliente,
        )
        resp, mock_pub = self._publish(outsider, "start")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        mock_pub.assert_not_called()
