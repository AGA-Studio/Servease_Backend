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
        ("ubicacion", "Ubicación"),
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
    # Path dentro del bucket privado de Supabase Storage (mensajeria_archivos)
    # — NO un FileField en disco local: en despliegues con filesystem
    # efímero (gunicorn/Render/etc.) los archivos guardados localmente se
    # perdían en cada redeploy/reinicio de instancia.
    archivo_path = models.CharField(max_length=500, blank=True, default="")
    # Nombre original del archivo (el storage lo renombra para evitar
    # colisiones), para poder mostrarlo/inferir su tipo en el chat.
    archivo_nombre = models.CharField(max_length=255, blank=True, default="")
    latitud = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitud = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
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
    # Receptor: el otro participante de la conversación. NOT NULL porque el
    # remoto lo usa: trigger notificar_nuevo_mensaje() + vista_conversaciones.
    receptor = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="mensajes_recibidos",
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
