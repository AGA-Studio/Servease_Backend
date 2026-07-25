from django.db import models


class VistaPerfilCliente(models.Model):
    id_usuario = models.UUIDField(primary_key=True)
    nombre = models.CharField(max_length=255)
    url_foto_perfil = models.URLField(blank=True, null=True)
    fecha_registro = models.DateTimeField()
    num_publicaciones = models.IntegerField()
    rating = models.FloatField()
    num_reviews = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'vista_perfil_cliente'
