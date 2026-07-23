from django.db import models


class Conversacion(models.Model):
    id_conversacion = models.AutoField(primary_key=True)
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=50)
    servicio = models.ForeignKey('servicios.Servicio', on_delete=models.CASCADE, related_name='conversaciones')
    cliente = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE, related_name='conversaciones_como_cliente')
    proveedor = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE, related_name='conversaciones_como_proveedor')

    class Meta:
        db_table = 'conversacion'

    def __str__(self):
        return f"Conversacion {self.id_conversacion}"