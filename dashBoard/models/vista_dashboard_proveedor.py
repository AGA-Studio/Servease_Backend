from django.db import models


class VistaDashboardProveedor(models.Model):
    proveedor_id = models.UUIDField(primary_key=True)

    trabajos_activos = models.IntegerField()
    trabajos_activos_nuevos_semana = models.IntegerField()
    trabajos_activos_nuevos_semana_pasada = models.IntegerField()
    trabajos_activos_pct_cambio = models.DecimalField(
        max_digits=10,
        decimal_places=1,
        null=True
    )

    trabajos_completados = models.IntegerField()
    completados_semana = models.IntegerField()
    completados_semana_pasada = models.IntegerField()
    completados_pct_cambio = models.DecimalField(
        max_digits=10,
        decimal_places=1,
        null=True
    )

    ganancias_totales = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True
    )

    ganancias_semana = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True
    )

    ganancias_semana_pasada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True
    )

    ganancias_pct_cambio = models.DecimalField(
        max_digits=10,
        decimal_places=1,
        null=True
    )

    promedio_calificacion = models.FloatField()

    num_reviews = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'vista_dashboard_proveedor'