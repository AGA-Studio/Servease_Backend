from django.db import models

from .conversacion import Conversacion


class Mensaje(models.Model):
    ESTADO_ENTREGA_CHOICES = (
        ("enviado", "Enviado"),
        ("recibido", "Recibido"),
        ("leido", "Leído"),
    )
    TIPO_MENSAJE_CHOICES = (
        ("texto", "Texto"),
        ("archivo", "Archivo"),
    )

    id_mensaje = models.AutoField(primary_key=True)
    contenido = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False)
    editado = models.BooleanField(default=False)
    estado_entrega = models.CharField(
        max_length=20, choices=ESTADO_ENTREGA_CHOICES, default="enviado"
    )
    tipo_mensaje = models.CharField(
        max_length=20, choices=TIPO_MENSAJE_CHOICES, default="texto"
    )
    archivo = models.FileField(upload_to="mensajes/archivos/", null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respuestas",
    )
    conversacion = models.ForeignKey(
        Conversacion, on_delete=models.CASCADE, related_name="mensajes"
    )
    emisor = models.ForeignKey(
        "usuarios.Usuario", on_delete=models.CASCADE, related_name="mensajes_enviados"
    )

    class Meta:
        db_table = "mensaje"
        ordering = ("fecha",)
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["conversacion", "fecha"],
                name="msg_conversacion_fecha_idx",
            ),
            models.Index(
                fields=["deleted_at"],
                name="msg_deleted_at_idx",
            ),
        ]

    def __str__(self):
        return f"Mensaje {self.id_mensaje}"
