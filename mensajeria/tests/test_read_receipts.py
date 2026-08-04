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
class ReadReceiptTests(TestCase):
    """Integration tests for mark-as-read endpoint."""

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

    # ─── PATCH /api/mensajeria/conversaciones/<id>/leido/ ───

    def test_mark_as_read(self):
        """PATCH marks unread messages from other user as read."""
        from mensajeria.models import Conversacion, Mensaje

        conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )
        Mensaje.objects.create(
            conversacion=conv,
            emisor=self.proveedor, receptor=self.cliente,
            contenido="Hola cliente",
            leido=False,
        )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/leido/",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

    def test_mark_as_read_only_marks_others_messages(self):
        """PATCH only marks messages from other user, not own."""
        from mensajeria.models import Conversacion, Mensaje

        conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )
        Mensaje.objects.create(
            conversacion=conv, emisor=self.cliente, receptor=self.proveedor, contenido="My msg", leido=False
        )
        Mensaje.objects.create(
            conversacion=conv, emisor=self.proveedor, receptor=self.cliente, contenido="Their msg", leido=False
        )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/leido/",
        )
        self.assertEqual(resp.data["count"], 1)
        my_msg = Mensaje.objects.get(conversacion=conv, emisor=self.cliente, receptor=self.proveedor)
        their_msg = Mensaje.objects.get(conversacion=conv, emisor=self.proveedor, receptor=self.cliente)
        self.assertFalse(my_msg.leido)
        self.assertTrue(their_msg.leido)

    def test_mark_as_read_returns_zero_when_all_read(self):
        """PATCH returns count=0 when no unread messages."""
        from mensajeria.models import Conversacion, Mensaje

        conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )
        Mensaje.objects.create(
            conversacion=conv,
            emisor=self.proveedor, receptor=self.cliente,
            contenido="Already read",
            leido=True,
        )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/leido/",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 0)

    def test_mark_as_read_non_participant_forbidden(self):
        """PATCH by non-participant returns 403."""
        from mensajeria.models import Conversacion

        conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )
        self.api_client.force_authenticate(user=self.cliente2)
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/leido/",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_mark_as_read_unauthenticated_fails(self):
        """Unauthenticated request returns 401."""
        from mensajeria.models import Conversacion

        conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/leido/",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_mark_as_read_multiple_messages(self):
        """PATCH marks multiple unread messages at once."""
        from mensajeria.models import Conversacion, Mensaje

        conv = Conversacion.objects.create(
            cliente=self.cliente, proveedor=self.proveedor
        )
        for i in range(5):
            Mensaje.objects.create(
                conversacion=conv,
                emisor=self.proveedor, receptor=self.cliente,
                contenido=f"Msg {i}",
                leido=False,
            )
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.patch(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/leido/",
        )
        self.assertEqual(resp.data["count"], 5)
        unread = Mensaje.objects.filter(
            conversacion=conv, emisor=self.proveedor, receptor=self.cliente, leido=False
        ).count()
        self.assertEqual(unread, 0)
