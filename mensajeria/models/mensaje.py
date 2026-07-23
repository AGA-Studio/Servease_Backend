from django.db import models
from .conversacion import Conversacion


class Mensaje(models.Model):
    id_mensaje = models.AutoField(primary_key=True)
    contenido = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False)
    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name='mensajes')
    emisor = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE, related_name='mensajes_enviados')
    receptor = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE, related_name='mensajes_recibidos')

    class Meta:
        db_table = 'mensaje'

    def __str__(self):
        return f"Mensaje {self.id_mensaje}"