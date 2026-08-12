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
class ConversationTests(TestCase):
    """Integration tests for conversation endpoints (CRUD + archive)."""

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
        self.admin = Usuario.objects.create(
            id_usuario="00000000-0000-0000-0000-000000000005",
            nombre="Admin",
            apellido_pa="User",
            correo="admin@test.com",
            rol=self.rol_admin,
        )

        self.client = APIClient()

    def _get_results(self, resp):
        """Extract results from paginated or non-paginated response."""
        if isinstance(resp.data, dict) and "results" in resp.data:
            return resp.data["results"]
        return resp.data

    # ─── POST /api/mensajeria/conversaciones/ ───

    def test_create_conversation_direct(self):
        """POST creates direct chat between client and provider."""
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(
            "/api/mensajeria/conversaciones/",
            {"proveedor_id": str(self.proveedor.id_usuario)},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", resp.data)
        self.assertEqual(
            resp.data["cliente"]["id_usuario"], str(self.cliente.id_usuario)
        )
        self.assertEqual(
            resp.data["proveedor"]["id_usuario"], str(self.proveedor.id_usuario)
        )

    def test_create_conversation_deduplication(self):
        """Creating same conversation twice returns existing (200, not 201)."""
        self.client.force_authenticate(user=self.cliente)
        resp1 = self.client.post(
            "/api/mensajeria/conversaciones/",
            {"proveedor_id": str(self.proveedor.id_usuario)},
            format="json",
        )
        resp2 = self.client.post(
            "/api/mensajeria/conversaciones/",
            {"proveedor_id": str(self.proveedor.id_usuario)},
            format="json",
        )
        self.assertEqual(resp1.data["id"], resp2.data["id"])
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)

    def test_create_conversation_with_self_fails(self):
        """Cannot create conversation with yourself."""
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(
            "/api/mensajeria/conversaciones/",
            {"proveedor_id": str(self.cliente.id_usuario)},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_conversation_nonexistent_provider_fails(self):
        """Provider ID that doesn't exist returns 400."""
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(
            "/api/mensajeria/conversaciones/",
            {"proveedor_id": "00000000-0000-0000-0000-999999999999"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_conversation_non_provider_user_fails(self):
        """Provider ID pointing to a client (rol_id=1) returns 400."""
        self.client.force_authenticate(user=self.cliente2)
        resp = self.client.post(
            "/api/mensajeria/conversaciones/",
            {"proveedor_id": str(self.cliente.id_usuario)},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_conversation_missing_proveedor_id_fails(self):
        """Missing proveedor_id returns 400."""
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(
            "/api/mensajeria/conversaciones/",
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_conversation_unauthenticated_fails(self):
        """Unauthenticated request returns 401."""
        resp = self.client.post(
            "/api/mensajeria/conversaciones/",
            {"proveedor_id": str(self.proveedor.id_usuario)},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ─── GET /api/mensajeria/conversaciones/ ───

    def test_list_conversations(self):
        """GET returns user's active conversations."""
        from mensajeria.models import Conversacion

        Conversacion.objects.create(cliente=self.cliente, proveedor=self.proveedor)
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get("/api/mensajeria/conversaciones/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertEqual(len(results), 1)

    def test_list_conversations_empty(self):
        """GET returns empty list when no conversations."""
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get("/api/mensajeria/conversaciones/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertEqual(len(results), 0)

    def test_list_conversations_includes_archived(self):
        """GET returns both active and archived conversations, flagged via
        `archivada`, so the frontend can split them into active/past
        sections instead of losing archived chats from the list."""
        from mensajeria.models import Conversacion
        from servicios.models.estado import ACTIVA, ARCHIVADA

        conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor, estado_id=ACTIVA
        )
        conv_archivada = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor2, estado_id=ARCHIVADA
        )
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get("/api/mensajeria/conversaciones/")
        results = self._get_results(resp)
        self.assertEqual(len(results), 2)
        by_id = {r["id"]: r for r in results}
        self.assertFalse(by_id[conv.id_conversacion]["archivada"])
        self.assertTrue(by_id[conv_archivada.id_conversacion]["archivada"])

    def test_list_conversations_search_by_name(self):
        """GET ?q= filters by other participant's name."""
        from mensajeria.models import Conversacion

        Conversacion.objects.create(cliente=self.cliente, proveedor=self.proveedor)
        Conversacion.objects.create(cliente=self.cliente, proveedor=self.proveedor2)
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get("/api/mensajeria/conversaciones/", {"q": "Sara"})
        results = self._get_results(resp)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Sara Jimenez")

    def test_list_conversations_provider_sees_their_chats(self):
        """Provider can see conversations where they participate."""
        from mensajeria.models import Conversacion

        Conversacion.objects.create(cliente=self.cliente, proveedor=self.proveedor)
        Conversacion.objects.create(cliente=self.cliente2, proveedor=self.proveedor)
        self.client.force_authenticate(user=self.proveedor)
        resp = self.client.get("/api/mensajeria/conversaciones/")
        results = self._get_results(resp)
        self.assertEqual(len(results), 2)

    def test_list_conversations_unauthenticated_fails(self):
        """Unauthenticated request returns 401."""
        resp = self.client.get("/api/mensajeria/conversaciones/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_conversations_response_shape(self):
        """Response has correct fields for frontend Chat interface."""
        from mensajeria.models import Conversacion

        Conversacion.objects.create(
            cliente=self.cliente,
            proveedor=self.proveedor,
            ultimo_mensaje_preview="Hola!",
            ultimo_mensaje_fecha=None,
        )
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get("/api/mensajeria/conversaciones/")
        results = self._get_results(resp)
        self.assertEqual(len(results), 1)
        chat = results[0]
        self.assertIn("id", chat)
        self.assertIn("name", chat)
        self.assertIn("avatar", chat)
        self.assertIn("professionKey", chat)
        self.assertIn("lastMessagePreview", chat)
        self.assertIn("timeAgoKey", chat)
        self.assertIn("unreadCount", chat)

    # ─── GET /api/mensajeria/conversaciones/<id>/ ───

    def test_conversation_detail(self):
        """GET returns conversation detail with both users."""
        from mensajeria.models import Conversacion
        from servicios.models.estado import ARCHIVADA

        conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            resp.data["cliente"]["id_usuario"], str(self.cliente.id_usuario)
        )
        self.assertEqual(
            resp.data["proveedor"]["id_usuario"], str(self.proveedor.id_usuario)
        )

    def test_conversation_detail_nonexistent_returns_404(self):
        """GET non-existent conversation returns 404."""
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get("/api/mensajeria/conversaciones/99999/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_conversation_detail_non_participant_forbidden(self):
        """GET conversation detail by non-participant returns 403."""
        from mensajeria.models import Conversacion

        conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )
        self.client.force_authenticate(user=self.cliente2)
        resp = self.client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_conversation_detail_unauthenticated_fails(self):
        """Unauthenticated request returns 401."""
        from mensajeria.models import Conversacion

        conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )
        resp = self.client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ─── DELETE /api/mensajeria/conversaciones/<id>/ ───

    def test_archive_conversation(self):
        """DELETE archives a conversation (sets estado='archivada')."""
        from mensajeria.models import Conversacion
        from servicios.models.estado import ARCHIVADA

        conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.delete(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        conv.refresh_from_db()
        self.assertEqual(conv.estado_id, ARCHIVADA)

    def test_archive_conversation_non_participant_forbidden(self):
        """DELETE by non-participant returns 403."""
        from mensajeria.models import Conversacion

        conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )
        self.client.force_authenticate(user=self.cliente2)
        resp = self.client.delete(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_archive_conversation_nonexistent_returns_404(self):
        """DELETE non-existent conversation returns 404."""
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.delete("/api/mensajeria/conversaciones/99999/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_archive_conversation_unauthenticated_fails(self):
        """Unauthenticated request returns 401."""
        from mensajeria.models import Conversacion

        conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )
        resp = self.client.delete(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
