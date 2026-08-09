from django.db import models


class VistaResumenGanancias(models.Model):
    proveedor_id = models.UUIDField(primary_key=True)
    ganancias_esta_semana = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_este_mes = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_pendiente = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_proyectado = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_totales = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_esta_semana_pct_cambio = models.DecimalField(
        max_digits=10, decimal_places=1, null=True
    )
    ganancias_este_mes_pct_cambio = models.DecimalField(
        max_digits=10, decimal_places=1, null=True
    )

    class Meta:
        managed = False
        db_table = 'vista_resumen_ganancias'