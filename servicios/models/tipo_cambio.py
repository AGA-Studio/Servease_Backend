from django.db import models


class TipoCambio(models.Model):
    id_tipo_cambio = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=10)

    class Meta:
        managed = True
        db_table = "tipo_cambio"

    def __str__(self):
        return self.nombre
