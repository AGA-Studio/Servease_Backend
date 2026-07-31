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
class SoftDeleteTests(TestCase):
    """Tests for soft-delete of messages (deleted_at field)."""

    def setUp(self):
        from usuarios.models import Rol, Usuario

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

        self.api_client = APIClient()

    def _create_conversation(self):
        from mensajeria.models import Conversacion

        return Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )

    def _get_results(self, resp):
        if isinstance(resp.data, dict) and "results" in resp.data:
            return resp.data["results"]
        return resp.data

    # ─── DELETE marks deleted_at instead of hard delete ───

    def test_delete_message_sets_deleted_at(self):
        """DELETE sets deleted_at instead of hard deleting."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        post_resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "To delete"},
            format="json",
        )
        msg_id = post_resp.data["id"]
        resp = self.api_client.delete(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg_id}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        # Message still exists but has deleted_at
        msg = Mensaje.objects.get(id_mensaje=msg_id)
        self.assertIsNotNone(msg.deleted_at)

    def test_deleted_message_excluded_from_list(self):
        """GET messages excludes soft-deleted messages."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        post_resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "To delete"},
            format="json",
        )
        msg_id = post_resp.data["id"]
        self.api_client.delete(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg_id}/"
        )
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertEqual(len(results), 0)

    def test_deleted_message_detail_returns_404(self):
        """GET detail of deleted message returns 404."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        post_resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "To delete"},
            format="json",
        )
        msg_id = post_resp.data["id"]
        self.api_client.delete(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg_id}/"
        )
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg_id}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_deleted_message_cannot_be_edited(self):
        """PATCH on deleted message returns 404."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        post_resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "To delete"},
            format="json",
        )
        msg_id = post_resp.data["id"]
        self.api_client.delete(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg_id}/"
        )
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg_id}/",
            {"contenido": "New content"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_deleted_message_still_exists_in_db(self):
        """Soft-deleted message still exists in DB (for audit)."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        post_resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "To delete"},
            format="json",
        )
        msg_id = post_resp.data["id"]
        self.api_client.delete(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg_id}/"
        )
        # Should still exist in DB with deleted_at
        self.assertTrue(Mensaje.objects.filter(id_mensaje=msg_id).exists())
        msg = Mensaje.objects.get(id_mensaje=msg_id)
        self.assertIsNotNone(msg.deleted_at)
