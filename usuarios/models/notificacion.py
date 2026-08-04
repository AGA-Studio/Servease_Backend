

from django.db import models

class Notificacion(models.Model):
    id_notificacion = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(
        'Usuario', on_delete=models.CASCADE,
        db_column='id_usuario', related_name='notificaciones'
    )
    tipo = models.CharField(max_length=50)
    titulo = models.CharField(max_length=150)
    contenido = models.TextField(blank=True, null=True)
    leido = models.BooleanField(default=False)
    fecha = models.DateTimeField()
    referencia_tabla = models.CharField(max_length=50, blank=True, null=True)
    referencia_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'notificacion'