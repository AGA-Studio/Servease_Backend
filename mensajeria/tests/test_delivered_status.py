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
class DeliveredStatusTests(TestCase):
    """Tests for message delivery status (enviado/recibido/leido)."""

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

    # ─── Message creation sets estado_entrega = 'enviado' ───

    def test_send_message_sets_estado_entrega_enviado(self):
        """POST message sets estado_entrega to 'enviado'."""
        from mensajeria.models import Mensaje

        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Hola"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["estado_entrega"], "enviado")
        msg = Mensaje.objects.get(id_mensaje=resp.data["id"])
        self.assertEqual(msg.estado_entrega, "enviado")

    # ─── WebSocket delivery updates estado_entrega to 'recibido' ───

    def test_ws_delivery_updates_to_recibido(self):
        """When recipient connects via WS, message estado_entrega becomes 'recibido'."""
        # This test requires WebSocket integration - will be implemented in WS tests


# PYEOF
