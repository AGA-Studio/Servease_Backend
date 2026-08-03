from django.db import models

class VistaConversaciones(models.Model):
    id_conversacion = models.IntegerField(primary_key=True)
    fecha_inicio = models.DateTimeField()
    estado = models.CharField(max_length=50)
    servicio_id = models.IntegerField()
    servicio_titulo = models.CharField(max_length=150)
    cliente_id = models.UUIDField()
    nombre_cliente = models.CharField(max_length=255)
    foto_cliente = models.URLField(blank=True, null=True)
    proveedor_id = models.UUIDField()
    nombre_proveedor = models.CharField(max_length=255)
    foto_proveedor = models.URLField(blank=True, null=True)
    ultimo_mensaje = models.TextField(blank=True, null=True)
    fecha_ultimo_mensaje = models.DateTimeField(blank=True, null=True)
    no_leidos_cliente = models.IntegerField()
    no_leidos_proveedor = models.IntegerField()
 
    class Meta:
        managed = False
        db_table = 'vista_conversaciones'