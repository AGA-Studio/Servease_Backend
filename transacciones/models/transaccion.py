from django.db import models


class Transaccion(models.Model):
    id_transaccion = models.AutoField(primary_key=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    comision = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=50)
    servicio = models.ForeignKey('servicios.Servicio', on_delete=models.CASCADE, related_name='transacciones')
    proveedor = models.ForeignKey('usuarios.Usuario', on_delete=models.PROTECT, related_name='transacciones_como_proveedor')
    cliente = models.ForeignKey('usuarios.Usuario', on_delete=models.PROTECT, related_name='transacciones_como_cliente')

    class Meta:
        db_table = 'transaccion'

    def __str__(self):
        return f"Transaccion {self.id_transaccion}"