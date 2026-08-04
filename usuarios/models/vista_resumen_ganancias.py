from django.db import models


class VistaResumenGanancias(models.Model):
    proveedor_id = models.UUIDField(primary_key=True)
    ganancias_esta_semana = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_este_mes = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_pendiente = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_proyectado = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'vista_resumen_ganancias'