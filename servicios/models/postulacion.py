from django.db import models
from .servicio import Servicio


class Postulacion(models.Model):
    id_postulacion = models.AutoField(primary_key=True)
    fecha = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now_add=True)  # la llena el trigger en la BD, Django solo la lee
    precio_propuesto = models.DecimalField(max_digits=10, decimal_places=2)
    mensaje = models.TextField(blank=True, null=True)
    estado = models.ForeignKey('Estado', on_delete=models.PROTECT, related_name='postulaciones')
    proveedor = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE, related_name='postulaciones')
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE, related_name='postulaciones')

    class Meta:
        db_table = 'postulacion'

    def __str__(self):
        return f"Postulacion {self.id_postulacion}"