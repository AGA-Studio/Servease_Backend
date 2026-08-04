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
class MessagePaginationTests(TestCase):
    """Tests for paginated message listing."""

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

    def test_list_messages_paginated_response_shape(self):
        """GET messages returns paginated response with count, next, previous, results."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        for i in range(60):
            Mensaje.objects.create(
                conversacion=conv,
                emisor=self.cliente if i % 2 == 0 else self.proveedor,
                receptor=self.proveedor if i % 2 == 0 else self.cliente,
                contenido=f"Msg {i}",
            )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("count", resp.data)
        self.assertIn("next", resp.data)
        self.assertIn("previous", resp.data)
        self.assertIn("results", resp.data)
        self.assertEqual(resp.data["count"], 60)
        self.assertEqual(len(resp.data["results"]), 50)  # default page size

    def test_list_messages_page_size_customizable(self):
        """GET messages with page_size parameter returns that many results."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        for i in range(30):
            Mensaje.objects.create(
                conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido=f"Msg {i}"
            )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"page_size": 10},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 10)

    def test_list_messages_pagination_next_previous(self):
        """Pagination next/previous links work correctly."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        for i in range(60):
            Mensaje.objects.create(
                conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido=f"Msg {i}"
            )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/"
        )
        self.assertIsNotNone(resp.data["next"])
        self.assertIsNone(resp.data["previous"])

        # Follow next link
        next_resp = self.api_client.get(resp.data["next"])
        self.assertEqual(next_resp.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(next_resp.data["previous"])
        self.assertEqual(len(next_resp.data["results"]), 10)  # remaining 10

    def test_list_messages_cursor_pagination_before_param(self):
        """?before=id cursor pagination still works alongside page pagination."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        msgs = [
            Mensaje.objects.create(
                conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido=f"Msg {i}"
            )
            for i in range(10)
        ]
        self.api_client.force_authenticate(user=self.cliente)
        # Use before_id to get messages older than a specific message
        before_id = msgs[5].id_mensaje
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"before": before_id},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertEqual(len(results), 5)

    def test_list_messages_pagination_unauthenticated_fails(self):
        conv = self._create_conversation()
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework.authentication.SessionAuthentication",
        ],
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    }
)
class ConversationPaginationTests(TestCase):
    """Tests for paginated conversation listing."""

    def setUp(self):
        self.rol_cliente = Rol.objects.create(id_rol=1, nombre="Cliente")
        self.rol_proveedor = Rol.objects.create(id_rol=2, nombre="Proveedor")
        self.cliente = Usuario.objects.create(
            id_usuario="00000000-0000-0000-0000-000000000001",
            nombre="Juan",
            apellido_pa="Perez",
            correo="juan@test.com",
            rol=Rol.objects.get(id_rol=1),
        )
        self.proveedor = Usuario.objects.create(
            id_usuario="00000000-0000-0000-0000-000000000002",
            nombre="Sara",
            apellido_pa="Jimenez",
            correo="sara@test.com",
            rol=Rol.objects.get(id_rol=2),
        )
        self.proveedor2 = Usuario.objects.create(
            id_usuario="00000000-0000-0000-0000-000000000003",
            nombre="Carlos",
            apellido_pa="Lopez",
            correo="carlos@test.com",
            rol=Rol.objects.get(id_rol=2),
        )
        self.proveedor3 = Usuario.objects.create(
            id_usuario="00000000-0000-0000-0000-000000000004",
            nombre="Maria",
            apellido_pa="Garcia",
            correo="maria@test.com",
            rol=Rol.objects.get(id_rol=2),
        )
        self.api_client = APIClient()

    def _create_conversations(self, count):
        from mensajeria.models import Conversacion

        proveedores = [self.proveedor, self.proveedor2, self.proveedor3]
        for i in range(count):
            Conversacion.objects.create(
                cliente=self.cliente,
                proveedor=proveedores[i % 3],
                ultimo_mensaje_preview=f"Msg {i}",
                ultimo_mensaje_fecha=None,
            )

    def _get_results(self, resp):
        if isinstance(resp.data, dict) and "results" in resp.data:
            return resp.data["results"]
        return resp.data

    def test_list_conversations_paginated(self):
        """GET conversations returns paginated response."""
        self._create_conversations(25)
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.get("/api/mensajeria/conversaciones/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("count", resp.data)
        self.assertIn("next", resp.data)
        self.assertIn("previous", resp.data)
        self.assertIn("results", resp.data)
        self.assertEqual(resp.data["count"], 25)
        self.assertEqual(len(resp.data["results"]), 20)  # default page size

    def test_list_conversations_page_size(self):
        """page_size parameter works for conversations."""
        self._create_conversations(15)
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.get("/api/mensajeria/conversaciones/", {"page_size": 5})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 5)

    def test_list_conversations_pagination_links(self):
        """next/previous links work for conversations."""
        self._create_conversations(25)
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.get("/api/mensajeria/conversaciones/")
        self.assertIsNotNone(resp.data["next"])
        self.assertIsNone(resp.data["previous"])

        next_resp = self.api_client.get(resp.data["next"])
        self.assertEqual(next_resp.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(next_resp.data["previous"])
        self.assertEqual(len(next_resp.data["results"]), 5)
