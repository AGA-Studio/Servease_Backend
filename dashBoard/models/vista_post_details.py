from django.db import models


class VistaPostDetails(models.Model):
    id_servicio = models.IntegerField(primary_key=True)
    titulo = models.CharField(max_length=150)

    latitud = models.DecimalField(
        max_digits=9,
        decimal_places=6
    )
    longitud = models.DecimalField(
        max_digits=9,
        decimal_places=6
    )

    fecha = models.DateTimeField()

    estado = models.CharField(max_length=50)

    categoria = models.CharField(max_length=100)

    precio_inicial = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    imagenes = models.JSONField(
        blank=True,
        null=True
    )

    descripcion = models.TextField()

    tiempo_transcurrido = models.DurationField()

    cliente_id = models.UUIDField()

    url_foto_perfil = models.TextField(
        blank=True,
        null=True
    )

    nombre_cliente = models.CharField(
        max_length=200
    )

    cliente_fecha_registro = models.DateTimeField()

    rating_cliente = models.FloatField()

    num_reviews_cliente = models.IntegerField()

    total_publicaciones_cliente = models.IntegerField()

    num_postulantes = models.IntegerField()

    moneda = models.CharField(
        max_length=10,
        blank=True,
        null=True
    )

    class Meta:
        managed = False
        db_table = 'vista_post_details'