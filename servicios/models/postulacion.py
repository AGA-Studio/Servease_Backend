from django.db import models
from .servicio import Servicio


class Postulacion(models.Model):
    id_postulacion = models.AutoField(primary_key=True)
    fecha = models.DateTimeField(auto_now_add=True)
    precio_propuesto = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=50)
    proveedor = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE, related_name='postulaciones')
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE, related_name='postulaciones')

    class Meta:
        db_table = 'postulacion'

    def __str__(self):
        return f"Postulacion {self.id_postulacion}"