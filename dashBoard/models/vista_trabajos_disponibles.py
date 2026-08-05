from django.contrib.postgres.fields import ArrayField
from django.db import models


class VistaTrabajosDisponibles(models.Model):
    id_servicio = models.IntegerField(primary_key=True)
    titulo = models.CharField(max_length=150)
    descripcion = models.TextField()
    categoria = models.CharField(max_length=100)
    categoria_id = models.IntegerField()
    latitud_aprox = models.DecimalField(max_digits=9, decimal_places=6)
    longitud_aprox = models.DecimalField(max_digits=9, decimal_places=6)
    fecha = models.DateTimeField()
    tiempo_transcurrido = models.DurationField()
    precio_inicial = models.DecimalField(max_digits=10, decimal_places=2)
    moneda = models.CharField(max_length=10, blank=True, null=True)
    estado_id = models.IntegerField()
    num_postulantes = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'vista_trabajos_disponibles'

        