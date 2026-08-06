from django.db import models

from servicios.models.estado import ACTIVA, ARCHIVADA


class Conversacion(models.Model):
    id_conversacion = models.AutoField(primary_key=True)
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    # FK al catálogo compartido de estados (estandarización del equipo).
    # "Activa"/"Archivada" viven en la tabla `estado` (ver servicios/estado.py).
    estado = models.ForeignKey(
        "servicios.Estado",
        on_delete=models.PROTECT,
        related_name="conversaciones",
        default=ACTIVA,
    )
    servicio = models.ForeignKey(
        "servicios.Servicio",
        on_delete=models.CASCADE,
        related_name="conversaciones",
        null=True,
        blank=True,
    )
    cliente = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="conversaciones_como_cliente",
    )
    proveedor = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="conversaciones_como_proveedor",
    )

    # Denormalized for fast list queries
    ultimo_mensaje_preview = models.CharField(max_length=200, blank=True, default="")
    ultimo_mensaje_fecha = models.DateTimeField(null=True, blank=True)
    # Denormalized unread count for performance
    unread_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "conversacion"
        unique_together = (("cliente", "proveedor", "servicio"),)
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["cliente", "ultimo_mensaje_fecha"],
                name="conv_cliente_fecha_idx",
            ),
            models.Index(
                fields=["proveedor", "ultimo_mensaje_fecha"],
                name="conv_proveedor_fecha_idx",
            ),
        ]

    def __str__(self):
        return f"Conversacion {self.id_conversacion}"
