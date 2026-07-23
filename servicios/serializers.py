from django.conf import settings
from rest_framework import serializers

from usuarios.models import Categoria
from .models import Servicio


class ServicioSerializer(serializers.ModelSerializer):
    id_cliente = serializers.UUIDField(source='cliente_id')
    id_categoria = serializers.IntegerField(source='categoria_id')

    class Meta:
        model = Servicio
        fields = [
            'id_servicio', 'titulo', 'descripcion', 'precio_inicial',
            'latitud', 'longitud', 'fecha', 'estado', 'imagenes',
            'fecha_final', 'id_cliente', 'id_categoria',
        ]


class CreateServicioSerializer(serializers.ModelSerializer):
    id_categoria = serializers.PrimaryKeyRelatedField(
        source='categoria', queryset=Categoria.objects.all()
    )
    imagenes = serializers.ListField(
        child=serializers.URLField(max_length=500), required=False, default=list
    )

    class Meta:
        model = Servicio
        fields = [
            'titulo', 'descripcion', 'precio_inicial',
            'latitud', 'longitud', 'imagenes', 'id_categoria',
        ]

    def validate_imagenes(self, value):
        usuario = self.context['request'].user
        expected_prefix = (
            f'{settings.SUPABASE_URL}/storage/v1/object/public/'
            f'service_images/user_{usuario.id_usuario}/'
        )
        for url in value:
            if not url.startswith(expected_prefix):
                raise serializers.ValidationError(
                    'Las imágenes deben apuntar a tu propia carpeta en el '
                    'bucket de imágenes de servicios.'
                )
        return value

    def create(self, validated_data):
        validated_data['cliente'] = self.context['request'].user
        validated_data['estado'] = 'pendiente'
        return Servicio.objects.create(**validated_data)
