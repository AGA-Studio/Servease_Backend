from django.db import models


class Empresa(models.Model):
    id_empresa = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    colonia = models.CharField(max_length=150)
    calle = models.CharField(max_length=150)
    cp = models.CharField(max_length=10)
    num_int = models.CharField(max_length=10, blank=True, null=True)
    num_ext = models.CharField(max_length=10)
    estado = models.CharField(max_length=50)
    contacto = models.CharField(max_length=150)

    class Meta:
        db_table = 'empresa'

    def __str__(self):
        return self.nombre