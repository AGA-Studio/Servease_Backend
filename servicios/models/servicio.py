from django.contrib.postgres.fields import ArrayField
from django.db import models


class Servicio(models.Model):
    id_servicio = models.AutoField(primary_key=True)
    titulo = models.CharField(max_length=150)
    descripcion = models.TextField()
    precio_inicial = models.DecimalField(max_digits=10, decimal_places=2)
    latitud = models.DecimalField(max_digits=9, decimal_places=6)
    longitud = models.DecimalField(max_digits=9, decimal_places=6)
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=50)
    imagenes = ArrayField(models.CharField(max_length=500), blank=True, default=list)
    fecha_final = models.DateTimeField(blank=True, null=True)
    cliente = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE, related_name='servicios_solicitados')
    categoria = models.ForeignKey('usuarios.Categoria', on_delete=models.PROTECT, related_name='servicios')

    class Meta:
        db_table = 'servicio'

    def __str__(self):
        return self.titulo