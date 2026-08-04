"""Tests de confirmación de lectura (read receipt) vía REST + Supabase Realtime.

Reemplaza los tests del channel layer de Channels: ahora MarcarLeidoView
persiste el cambio en BD y publica read_receipt con publish_event.
"""

import uuid
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from mensajeria.models import Conversacion, Mensaje
from usuarios.models import Rol, Usuario


class ReadReceiptTests(TestCase):
    """PATCH de lectura marca los mensajes y publica read_receipt."""

    def setUp(self):
        self.rol_cliente = Rol.objects.create(id_rol=1, nombre="Cliente")
        self.rol_proveedor = Rol.objects.create(id_rol=2, nombre="Proveedor")
        self.cliente = Usuario.objects.create(
            id_usuario=uuid.uuid4(),
            nombre="Cliente",
            apellido_pa="Test",
            correo=f"__VG_RR_CLIENT_{uuid.uuid4()}__",
            rol=self.rol_cliente,
        )
        self.proveedor = Usuario.objects.create(
            id_usuario=uuid.uuid4(),
            nombre="Proveedor",
            apellido_pa="Test",
            correo=f"__VG_RR_PROV_{uuid.uuid4()}__",
            rol=self.rol_proveedor,
        )
        self.conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )
        self.api_client = APIClient()
        self.url = f"/api/mensajeria/conversaciones/{self.conv.id_conversacion}/leido/"

    def _create_unread(self, emisor, contenido):
        return Mensaje.objects.create(
            conversacion=self.conv, emisor=emisor, receptor=self.proveedor if emisor == self.cliente else self.cliente, contenido=contenido, leido=False
        )

    def test_mark_read_updates_db_and_publishes(self):
        """Marca los mensajes no leídos del otro participante y publica read_receipt."""
        self._create_unread(self.proveedor, "Msg 1")
        self._create_unread(self.proveedor, "Msg 2")

        self.api_client.force_authenticate(user=self.cliente)
        with patch("mensajeria.views.publish_event") as mock_pub:
            resp = self.api_client.patch(self.url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 2)
        self.assertEqual(Mensaje.objects.filter(leido=True).count(), 2)

        mock_pub.assert_called_once()
        conv_id, event, payload = mock_pub.call_args.args
        self.assertEqual(conv_id, self.conv.id_conversacion)
        self.assertEqual(event, "read_receipt")
        self.assertEqual(payload["reader_id"], str(self.cliente.id_usuario))
        self.assertEqual(payload["count"], 2)

    def test_mark_read_does_not_touch_own_messages(self):
        """Los propios mensajes no se marcan como leídos."""
        self._create_unread(self.cliente, "Propio")
        self._create_unread(self.proveedor, "Ajeno")

        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.patch(self.url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        own = Mensaje.objects.get(contenido="Propio")
        self.assertFalse(own.leido)

    def test_no_unread_publishes_zero(self):
        """Sin mensajes pendientes: count 0 y publica read_receipt igual."""
        self.api_client.force_authenticate(user=self.cliente)
        with patch("mensajeria.views.publish_event") as mock_pub:
            resp = self.api_client.patch(self.url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 0)
        mock_pub.assert_called_once()
        self.assertEqual(mock_pub.call_args.args[1], "read_receipt")

    def test_non_participant_forbidden(self):
        """Un usuario fuera de la conversación no puede marcar leído."""
        self._create_unread(self.proveedor, "Msg")
        outsider = Usuario.objects.create(
            id_usuario=uuid.uuid4(),
            nombre="Outsider",
            apellido_pa="Test",
            correo=f"__VG_RR_OUT_{uuid.uuid4()}__",
            rol=self.rol_cliente,
        )
        self.api_client.force_authenticate(user=outsider)
        resp = self.api_client.patch(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
