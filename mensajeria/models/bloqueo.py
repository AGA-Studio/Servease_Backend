from django.db import models


class Bloqueo(models.Model):
    usuario_bloqueador = models.ForeignKey(
        "usuarios.Usuario", on_delete=models.CASCADE, related_name="bloqueos_realizados"
    )
    usuario_bloqueado = models.ForeignKey(
        "usuarios.Usuario", on_delete=models.CASCADE, related_name="bloqueos_recibidos"
    )
    motivo = models.CharField(max_length=200, blank=True, default="")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bloqueo"
        unique_together = (("usuario_bloqueador", "usuario_bloqueado"),)
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["usuario_bloqueador", "usuario_bloqueado"],
                name="bloqueo_bloq_bloq_idx",
            ),
        ]

    def __str__(self):
        return f"{self.usuario_bloqueador} bloqueó a {self.usuario_bloqueado}"
