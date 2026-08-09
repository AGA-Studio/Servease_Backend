from django.db import models


class VistaResumenGanancias(models.Model):
    """
    Cada bucket viene separado por moneda (MXN/USD, según servicio.tipo_cambio)
    en lugar de una sola suma: la vista sumaba montos en pesos y en dólares
    como si fueran la misma unidad. La conversión a una sola moneda de
    presentación (con la tasa vigente) se hace en el frontend, que ya trae
    integración con la API de tipo de cambio (ver CurrencyContext).
    `ganancias_proyectado` y los `_pct_cambio` se calculan también en el
    frontend, después de convertir, para que sean correctos.
    """

    proveedor_id = models.UUIDField(primary_key=True)
    ganancias_esta_semana_mxn = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_esta_semana_usd = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_este_mes_mxn = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_este_mes_usd = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_pendiente_mxn = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_pendiente_usd = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_totales_mxn = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_totales_usd = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_semana_anterior_mxn = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_semana_anterior_usd = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_mes_anterior_mxn = models.DecimalField(max_digits=12, decimal_places=2)
    ganancias_mes_anterior_usd = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'vista_resumen_ganancias'