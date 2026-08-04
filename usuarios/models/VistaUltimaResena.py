from django.contrib.postgres.fields import ArrayField
from django.db import models


class VistaUltimaResena(models.Model):
    id_calificacion = models.IntegerField(primary_key=True)
    puntuacion = models.SmallIntegerField()
    comentario = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField()
    tiempo_transcurrido = models.DurationField()
    nombre_evaluador = models.CharField(max_length=255)
    foto_evaluador = models.URLField(blank=True, null=True)
 
    class Meta:
        managed = False
        db_table = 'calificacion'  # no se usa de forma directa, solo existe para el .raw()
 