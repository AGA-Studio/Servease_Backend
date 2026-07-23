from django.db import models
from .empresa import Empresa


class Sucursal(models.Model):
    id_sucursal = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    colonia = models.CharField(max_length=150)
    calle = models.CharField(max_length=150)
    cp = models.CharField(max_length=10)
    num_int = models.CharField(max_length=10, blank=True, null=True)
    num_ext = models.CharField(max_length=10)
    estado = models.CharField(max_length=50)
    contacto = models.CharField(max_length=150)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='sucursales')

    class Meta:
        db_table = 'sucursal'

    def __str__(self):
        return self.nombre