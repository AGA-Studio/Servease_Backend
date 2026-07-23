from django.db import models


class VistaInfoAplicantes(models.Model):
    id_postulacion = models.IntegerField(primary_key=True)
    servicio_id = models.IntegerField()
    estado_solicitud = models.CharField(max_length=50)
    precio_propuesto = models.DecimalField(max_digits=10, decimal_places=2)
    mensaje_proveedor = models.TextField(blank=True, null=True)
    presupuesto_acordado = models.DecimalField(max_digits=10, decimal_places=2)
    proveedor_id = models.UUIDField()
    nombre_proveedor = models.CharField(max_length=255)
    url_foto_perfil = models.URLField(blank=True, null=True)
    rating = models.FloatField()
    num_reviews = models.IntegerField()
    trabajos_completados = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'vista_info_aplicantes'
