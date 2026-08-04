from django.contrib.postgres.fields import ArrayField 
from django.db import models
 
class PortafolioProveedor(models.Model):
    id_portafolio = models.AutoField(primary_key=True)
    proveedor = models.ForeignKey(
        'Usuario', on_delete=models.CASCADE, related_name='portafolio'
    )
    titulo = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    categoria = models.ForeignKey(
        'Categoria', on_delete=models.PROTECT, related_name='portafolios'
    )
    fotos = ArrayField(models.CharField(max_length=500), blank=True, default=list)
    fecha = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        managed = False
        db_table = 'portafolio_proveedor'
 
    def __str__(self):
        return self.titulo
 