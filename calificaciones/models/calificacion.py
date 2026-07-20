from django.db import models


class Calificacion(models.Model):
    id_calificacion = models.AutoField(primary_key=True)
    puntuacion = models.PositiveSmallIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)
    comentario = models.TextField(blank=True, null=True)
    servicio = models.ForeignKey('servicios.Servicio', on_delete=models.CASCADE, related_name='calificaciones')
    evaluador = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE, related_name='calificaciones_dadas')
    evaluado = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE, related_name='calificaciones_recibidas')

    class Meta:
        db_table = 'calificacion'

    def __str__(self):
        return f"Calificacion {self.id_calificacion}"