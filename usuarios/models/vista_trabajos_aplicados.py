from django.db import models
 
 
class VistaTrabajosAplicados(models.Model):
    id_postulacion = models.IntegerField(primary_key=True)
    proveedor_id = models.UUIDField()
    id_servicio = models.IntegerField()
    titulo = models.CharField(max_length=150)
    estado_id = models.IntegerField()
    estado = models.CharField(max_length=50)
    categoria_id = models.IntegerField()
    categoria = models.CharField(max_length=100)
    fecha_publicacion = models.DateTimeField()
    tiempo_transcurrido = models.DurationField()
    precio_final = models.DecimalField(max_digits=10, decimal_places=2)
    foto = models.URLField(max_length=500, blank=True, null=True)
    trabajo_terminado = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = 'vista_trabajos_aplicados'
 