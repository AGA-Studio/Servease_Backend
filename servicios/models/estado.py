from django.db import models


class Estado(models.Model):
    id_estado = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=50)

    class Meta:
        db_table = 'estado'

    def __str__(self):
        return self.descripcion


# Constantes para usar en el codigo en vez de numeros "magicos"
# (ej. servicio.estado_id = ABIERTO, en vez de servicio.estado_id = 7)
ACEPTADO = 1
PENDIENTE = 2
RECHAZADA = 3
PROGRESO = 4
COMPLETADO = 5
CONTRAOFERTA = 6
ABIERTO = 7
CANCELADO = 8
