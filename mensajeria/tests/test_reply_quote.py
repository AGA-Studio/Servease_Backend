from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from usuarios.models import Rol, Usuario


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework.authentication.SessionAuthentication",
        ],
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    }
)
class ReplyQuoteTests(TestCase):
    """Tests for replying/quoting messages (reply_to field)."""

    def setUp(self):

        self.rol_cliente = Rol.objects.create(id_rol=1, nombre="Cliente")
        self.rol_proveedor = Rol.objects.create(id_rol=2, nombre="Proveedor")

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
        self.cliente2 = Usuario.objects.create(
            id_usuario="00000000-0000-0000-0000-000000000004",
            nombre="Maria",
            apellido_pa="Garcia",
            correo="maria@test.com",
            rol=self.rol_cliente,
        )
        self.proveedor2 = Usuario.objects.create(
            id_usuario="00000000-0000-0000-0000-000000000005",
            nombre="Carlos",
            apellido_pa="Lopez",
            correo="carlos@test.com",
            rol=self.rol_proveedor,
        )

        self.api_client = APIClient()

    def _create_conversation(self, cliente=None, proveedor=None):
        from mensajeria.models import Conversacion

        return Conversacion.objects.create(
            cliente=cliente or self.cliente, proveedor=proveedor or self.proveedor
        )

    # ─── POST with reply_to ───

    def test_send_message_with_reply_to(self):
        """POST message with reply_to creates threaded message."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        # Create original message
        orig_resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Mensaje original"},
            format="json",
        )
        orig_id = orig_resp.data["id"]
        # Reply to it
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Respuesta", "reply_to": orig_id},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["reply_to"], orig_id)
        self.assertEqual(resp.data["text"], "Respuesta")

    def test_reply_to_nonexistent_message_fails(self):
        """reply_to non-existent message returns 400."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Reply", "reply_to": 99999},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reply_to_message_from_other_conversation_fails(self):
        """reply_to message from different conversation returns 400."""
        from mensajeria.models import Mensaje

        conv1 = self._create_conversation()
        conv2 = self._create_conversation(
            cliente=self.cliente, proveedor=self.proveedor2
        )
        self.api_client.force_authenticate(user=self.cliente)
        msg1 = Mensaje.objects.create(
            conversacion=conv1, emisor=self.cliente, contenido="Msg 1"
        )
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv2.id_conversacion}/mensajes/",
            {"contenido": "Reply", "reply_to": msg1.id_mensaje},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reply_to_own_message_allowed(self):
        """Can reply to your own message."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        msg = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, contenido="My msg"
        )
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Reply to self", "reply_to": msg.id_mensaje},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["reply_to"], msg.id_mensaje)

    # ─── GET includes reply_to ───

    def test_list_messages_includes_reply_to(self):
        """GET messages includes reply_to field."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        msg1 = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, contenido="Original"
        )
        Mensaje.objects.create(
            conversacion=conv, emisor=self.proveedor, contenido="Reply", reply_to=msg1
        )
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Handle pagination
        results = resp.data.get("results", resp.data)
        reply_msg = next(m for m in results if m["text"] == "Reply")
        self.assertEqual(reply_msg["reply_to"], msg1.id_mensaje)

    def test_message_detail_includes_reply_to(self):
        """GET message detail includes reply_to."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        msg1 = Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, contenido="Original"
        )
        msg2 = Mensaje.objects.create(
            conversacion=conv, emisor=self.proveedor, contenido="Reply", reply_to=msg1
        )
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg2.id_mensaje}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["reply_to"], msg1.id_mensaje)
