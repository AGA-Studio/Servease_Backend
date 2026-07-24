from django.db import models
from django.contrib.postgres.fields import ArrayField

class VistaHomeCliente(models.Model):
    """Modelo no administrado: mapea a la vista SQL vista_home_cliente."""
    id_servicio = models.IntegerField(primary_key=True)
    titulo = models.CharField(max_length=150)
    descripcion = models.TextField()
    categoria = models.CharField(max_length=100)
    latitud = models.DecimalField(max_digits=9, decimal_places=6)
    longitud = models.DecimalField(max_digits=9, decimal_places=6)
    fecha = models.DateTimeField()
    tiempo_transcurrido = models.DurationField()
    estado = models.CharField(max_length=50)
    cliente_id = models.UUIDField()
    fotos_proveedores_aplicantes = ArrayField(
        models.CharField(max_length=500), blank=True, default=list
    )

    class Meta:
        managed = False
        db_table = 'vista_home_cliente'