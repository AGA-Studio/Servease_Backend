from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework.authentication.SessionAuthentication",
        ],
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    },
    MEDIA_ROOT="/tmp/test_media",
)
class AttachmentTests(TestCase):
    """Integration tests for message attachments (images, files)."""

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

    def _create_image_file(self, name="test.jpg", content=None):
        # Real JPEG magic bytes (\xff\xd8\xff) so server-side validation passes
        content = content if content is not None else b"\xff\xd8\xff\xe0" + b"fake image content"
        return SimpleUploadedFile(name, content, content_type="image/jpeg")

    def _create_pdf_file(self, name="test.pdf", content=None):
        # Real PDF magic bytes (%PDF-) so server-side validation passes
        content = content if content is not None else b"%PDF-1.4\n" + b"fake pdf content"
        return SimpleUploadedFile(name, content, content_type="application/pdf")

    def _get_results(self, resp):
        if isinstance(resp.data, dict) and "results" in resp.data:
            return resp.data["results"]
        return resp.data

    # ─── POST /api/mensajeria/conversaciones/<id>/mensajes/ with attachment ───

    def test_send_message_with_image_attachment(self):
        """POST with image file creates message with attachment."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        image = self._create_image_file()
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Mira esta foto", "archivo": image},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["text"], "Mira esta foto")
        self.assertEqual(resp.data["tipo_mensaje"], "archivo")
        self.assertIn("archivo", resp.data)
        self.assertTrue(resp.data["archivo"])
        self.assertEqual(resp.data["archivo_nombre"], "test.jpg")

    def test_send_message_with_pdf_attachment(self):
        """POST with PDF file creates message with attachment."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        pdf = self._create_pdf_file()
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Aquí está el documento", "archivo": pdf},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["tipo_mensaje"], "archivo")
        self.assertTrue(resp.data["archivo"])
        self.assertEqual(resp.data["archivo_nombre"], "test.pdf")

    def test_send_message_attachment_only_no_text(self):
        """POST with only attachment (no contenido) is valid."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        image = self._create_image_file()
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"archivo": image},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["text"], "")
        self.assertEqual(resp.data["tipo_mensaje"], "archivo")

    def test_send_message_invalid_file_type_rejected(self):
        """POST with executable file type returns 400."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        exe = SimpleUploadedFile(
            "malware.exe", b"MZ...", content_type="application/x-msdownload"
        )
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Malware", "archivo": exe},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # Error can be in 'archivo' or 'non_field_errors'
        self.assertTrue("archivo" in resp.data or "non_field_errors" in resp.data)

    def test_send_message_spoofed_content_type_rejected(self):
        """POST declaring image/jpeg but with non-image bytes returns 400."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        spoofed = SimpleUploadedFile(
            "evil.jpg", b"MZ\x90\x00binary", content_type="image/jpeg"
        )
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Spoof", "archivo": spoofed},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue("archivo" in resp.data or "non_field_errors" in resp.data)

    def test_send_message_file_too_large_rejected(self):
        """POST with file > 10MB returns 400."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        large_file = SimpleUploadedFile(
            "large.jpg", large_content, content_type="image/jpeg"
        )
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Large file", "archivo": large_file},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue("archivo" in resp.data or "non_field_errors" in resp.data)

    def test_send_message_attachment_non_participant_forbidden(self):
        """POST with attachment by non-participant returns 403."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente2)
        image = self._create_image_file()
        resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Intruder", "archivo": image},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ─── GET /api/mensajeria/conversaciones/<id>/mensajes/ includes attachments ───

    def test_list_messages_includes_attachment_fields(self):
        """GET messages returns attachment info in response."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        image = self._create_image_file()
        self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Con foto", "archivo": image},
            format="multipart",
        )
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        msg = results[0]
        self.assertEqual(msg["tipo_mensaje"], "archivo")
        self.assertIn("archivo", msg)
        self.assertTrue(msg["archivo"])

    def test_message_detail_includes_attachment(self):
        """GET message detail includes attachment URL."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        image = self._create_image_file()
        post_resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Detail test", "archivo": image},
            format="multipart",
        )
        msg_id = post_resp.data["id"]
        resp = self.api_client.get(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/{msg_id}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["tipo_mensaje"], "archivo")
        self.assertIn("archivo", resp.data)

    # ─── File download endpoint ───

    def test_download_attachment(self):
        """GET /api/mensajeria/mensajes/<id>/archivo/ returns file."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        image = self._create_image_file()
        post_resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Download test", "archivo": image},
            format="multipart",
        )
        msg_id = post_resp.data["id"]
        resp = self.api_client.get(f"/api/mensajeria/mensajes/{msg_id}/archivo/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp["Content-Type"], "image/jpeg")
        self.assertIn("attachment", resp["Content-Disposition"])

    def test_download_attachment_non_participant_forbidden(self):
        """Non-participant cannot download attachment."""
        conv = self._create_conversation()
        self.api_client.force_authenticate(user=self.cliente)
        image = self._create_image_file()
        post_resp = self.api_client.post(
            f"/api/mensajeria/conversaciones/{conv.id_conversacion}/mensajes/",
            {"contenido": "Secret", "archivo": image},
            format="multipart",
        )
        msg_id = post_resp.data["id"]
        self.api_client.force_authenticate(user=self.cliente2)
        resp = self.api_client.get(f"/api/mensajeria/mensajes/{msg_id}/archivo/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
