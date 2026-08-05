from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework.authentication.SessionAuthentication",
        ],
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    }
)
class MessageTests(TestCase):
    """Integration tests for message endpoints (list, send, detail, edit, delete)."""

    def setUp(self):
        from usuarios.models import Rol, Usuario

        self.rol_cliente = Rol.objects.create(id_rol=1, nombre="Cliente")
        self.rol_proveedor = Rol.objects.create(id_rol=2, nombre="Proveedor")
        self.rol_admin = Rol.objects.create(id_rol=3, nombre="Admin")

        self.cliente = Usuario.objects.create(
            id_usuario="00000000-0000-0000-0000-000000000001",
            nombre="Juan",
            apellido_pa="Perez",
            correo="juan@test.com",
            rol=self.rol_cliente,
        )
        self.proveedor = Usuario.objects.create(
            id_usuario="00000000-0000-0000-0000-000000000002",
            nombre="Sara",
            apellido_pa="Jimenez",
            correo="sara@test.com",
            rol=self.rol_proveedor,
        )
        self.proveedor2 = Usuario.objects.create(
            id_usuario="00000000-0000-0000-0000-000000000003",
            nombre="Carlos",
            apellido_pa="Lopez",
            correo="carlos@test.com",
            rol=self.rol_proveedor,
        )
        self.cliente2 = Usuario.objects.create(
            id_usuario="00000000-0000-0000-0000-000000000004",
            nombre="Maria",
            apellido_pa="Garcia",
            correo="maria@test.com",
            rol=self.rol_cliente,
        )

        self.api_client = APIClient()

    def _create_conversation(self):
        from mensajeria.models import Conversacion

        return Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )

    def _get_results(self, resp):
        """Extract results from paginated or non-paginated response."""
        if isinstance(resp.data, dict) and "results" in resp.data:
            return resp.data["results"]
        return resp.data

    # ─── GET /api/mensajeria/conversaciones/<id>/mensajes/ ───

    def test_list_messages(self):
        """GET returns messages in chronological order (oldest first)."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        Mensaje.objects.create(conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Hola")
        Mensaje.objects.create(
            conversacion=conv, emisor=self.proveedor, receptor=self.cliente, contenido="Hola!"
        )
        Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Como estas?"
        )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["text"], "Hola")
        self.assertEqual(results[1]["text"], "Hola!")
        self.assertEqual(results[2]["text"], "Como estas?")

    def test_list_messages_pagination_before(self):
        """GET ?before=id returns messages older than the given ID."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Msg 1"
        )
        Mensaje.objects.create(
            conversacion=conv, emisor=self.proveedor, receptor=self.cliente, contenido="Msg 2"
        )
        m3 = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Msg 3"
        )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"before": m3.id_mensaje},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["text"], "Msg 1")
        self.assertEqual(results[1]["text"], "Msg 2")

    def test_list_messages_empty(self):
        """GET returns empty list when no messages."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertEqual(len(results), 0)

    def test_list_messages_response_shape(self):
        """Response has correct fields for frontend Message interface."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        Mensaje.objects.create(conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Test")
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/"
        )
        results = self._get_results(resp)
        msg = results[0]
        self.assertIn("id", msg)
        self.assertIn("sender", msg)
        self.assertIn("senderName", msg)
        self.assertIn("senderAvatar", msg)
        self.assertIn("text", msg)
        self.assertIn("time", msg)
        self.assertIn("leido", msg)
        self.assertIn("editado", msg)

    def test_list_messages_sender_field(self):
        """sender is 'user' for own messages, 'other' for other's messages."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="My msg"
        )
        Mensaje.objects.create(
            conversacion=conv, emisor=self.proveedor, receptor=self.cliente, contenido="Their msg"
        )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/"
        )
        results = self._get_results(resp)
        my_msg = next(m for m in results if m["text"] == "My msg")
        their_msg = next(m for m in results if m["text"] == "Their msg")
        self.assertEqual(my_msg["sender"], "user")
        self.assertEqual(their_msg["sender"], "other")

    def test_list_messages_non_participant_forbidden(self):
        """GET messages by non-participant returns 403."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente2)
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_messages_unauthenticated_fails(self):
        """Unauthenticated request returns 401."""
        conv = self._create_conversation()
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ─── POST /api/mensajeria/conversaciones/<id>/mensajes/ ───

    def test_send_message(self):
        """POST creates a new message."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Hola, como estas?"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["text"], "Hola, como estas?")
        self.assertEqual(resp.data["sender"], "user")

    def test_send_message_updates_preview(self):
        """POST message updates conversacion denormalized preview fields."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Hola, como estas?"},
            format="json",
        )
        conv.refresh_from_db()
        self.assertEqual(conv.ultimo_mensaje_preview, "Hola, como estas?")
        self.assertIsNotNone(conv.ultimo_mensaje_fecha)

    def test_send_message_preview_truncated_at_200(self):
        """Preview is truncated at 200 characters."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "x" * 300},
            format="json",
        )
        conv.refresh_from_db()
        self.assertEqual(len(conv.ultimo_mensaje_preview), 200)

    def test_send_message_empty_content_fails(self):
        """POST with empty contenido returns 400."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": ""},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_message_whitespace_only_fails(self):
        """POST with whitespace-only contenido returns 400."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "   "},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_message_too_long_fails(self):
        """POST with contenido > 2000 chars returns 400."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "x" * 2001},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_message_non_participant_forbidden(self):
        """POST message by non-participant returns 403."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente2)
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Intruder!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_send_message_unauthenticated_fails(self):
        """Unauthenticated request returns 401."""
        conv = self._create_conversation()
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Hello"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_send_message_missing_contenido_fails(self):
        """POST without contenido returns 400."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ─── GET /api/mensajeria/conversaciones/<id>/mensajes/<msg_id>/ ───

    def test_message_detail(self):
        """GET returns single message with correct shape."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Test message"
        )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg.id_mensaje}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["id"], msg.id_mensaje)
        self.assertEqual(resp.data["text"], "Test message")
        self.assertEqual(resp.data["sender"], "user")
        self.assertIn("senderName", resp.data)
        self.assertIn("senderAvatar", resp.data)
        self.assertIn("time", resp.data)
        self.assertIn("leido", resp.data)
        self.assertIn("editado", resp.data)

    def test_message_detail_nonexistent_returns_404(self):
        """GET non-existent message returns 404."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/99999/"
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_message_detail_non_participant_forbidden(self):
        """GET message by non-participant returns 403."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Test"
        )
        self.api_client.force_authenticate(user=self.cliente2)
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg.id_mensaje}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_message_detail_unauthenticated_fails(self):
        """Unauthenticated GET message returns 401."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Test"
        )
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg.id_mensaje}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_message_detail_other_user_message_sender_other(self):
        """GET message from other user shows sender='other'."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.proveedor, receptor=self.cliente, contenido="From provider"
        )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg.id_mensaje}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["sender"], "other")
        self.assertEqual(resp.data["senderName"], "Sara Jimenez")

    # ─── PATCH /api/mensajeria/conversaciones/<id>/mensajes/<msg_id>/ ───

    def test_edit_message_success(self):
        """PATCH edits message content, sets editado=True."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Original"
        )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg.id_mensaje}/",
            {"contenido": "Edited content"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["text"], "Edited content")
        self.assertIn("leido", resp.data)
        msg.refresh_from_db()
        self.assertEqual(msg.contenido, "Edited content")
        self.assertTrue(msg.editado)

    def test_edit_message_only_emisor_can_edit(self):
        """PATCH by non-emisor returns 403."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Original"
        )
        self.api_client.force_authenticate(user=self.proveedor)
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg.id_mensaje}/",
            {"contenido": "Hack attempt"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        msg.refresh_from_db()
        self.assertEqual(msg.contenido, "Original")
        self.assertFalse(msg.editado)

    def test_edit_message_empty_content_fails(self):
        """PATCH with empty contenido returns 400."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Original"
        )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg.id_mensaje}/",
            {"contenido": ""},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_edit_message_whitespace_only_fails(self):
        """PATCH with whitespace-only contenido returns 400."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Original"
        )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg.id_mensaje}/",
            {"contenido": "   "},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_edit_message_too_long_fails(self):
        """PATCH with contenido > 2000 chars returns 400."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Original"
        )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg.id_mensaje}/",
            {"contenido": "x" * 2001},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_edit_message_missing_contenido_fails(self):
        """PATCH without contenido returns 400."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Original"
        )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg.id_mensaje}/",
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_edit_message_nonexistent_returns_404(self):
        """PATCH non-existent message returns 404."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/99999/",
            {"contenido": "New content"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_edit_message_non_participant_forbidden(self):
        """PATCH by non-participant returns 403."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Original"
        )
        self.api_client.force_authenticate(user=self.cliente2)
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg.id_mensaje}/",
            {"contenido": "Hack"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_edit_message_unauthenticated_fails(self):
        """Unauthenticated PATCH returns 401."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="Original"
        )
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg.id_mensaje}/",
            {"contenido": "New"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ─── DELETE /api/mensajeria/conversaciones/<id>/mensajes/<msg_id>/ ───

    def test_delete_message_success(self):
        """DELETE by emisor removes message (hard delete)."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="To delete"
        )
        msg_id = msg.id_mensaje
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.delete(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg_id}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        msg = Mensaje.objects.get(id_mensaje=msg_id)
        self.assertIsNotNone(msg.deleted_at)

    def test_delete_message_only_emisor_can_delete(self):
        """DELETE by non-emisor returns 403."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="To delete"
        )
        self.api_client.force_authenticate(user=self.proveedor)
        resp = self.api_client.delete(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg.id_mensaje}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Mensaje.objects.filter(id_mensaje=msg.id_mensaje).exists())

    def test_delete_message_nonexistent_returns_404(self):
        """DELETE non-existent message returns 404."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.delete(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/99999/"
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_message_non_participant_forbidden(self):
        """DELETE by non-participant returns 403."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="To delete"
        )
        self.api_client.force_authenticate(user=self.cliente2)
        resp = self.api_client.delete(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg.id_mensaje}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_message_unauthenticated_fails(self):
        """Unauthenticated DELETE returns 401."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="To delete"
        )
        resp = self.api_client.delete(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg.id_mensaje}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
