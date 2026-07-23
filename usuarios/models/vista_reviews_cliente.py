from django.db import models


class VistaReviewsCliente(models.Model):
    id_calificacion = models.IntegerField(primary_key=True)
    cliente_id = models.UUIDField()
    puntuacion = models.PositiveSmallIntegerField()
    comentario = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField()
    nombre_evaluador = models.CharField(max_length=255)
    foto_evaluador = models.URLField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'vista_reviews_cliente'
