from django.db import models
from .postulacion import Postulacion


class Oferta(models.Model):
    id_oferta = models.AutoField(primary_key=True)
    aceptacion = models.BooleanField(default=False)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.ForeignKey(
        'servicios.Estado', on_delete=models.PROTECT,
        db_column='estado_id', related_name='ofertas',
    )
    comentario = models.TextField(blank=True, null=True)
    postulacion = models.ForeignKey(Postulacion, on_delete=models.CASCADE, related_name='ofertas')
    emisor = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ofertas_enviadas',
    )

    class Meta:
        db_table = 'oferta'

    def __str__(self):
        return f"Oferta {self.id_oferta}"