from decimal import Decimal

from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from usuarios.models import Categoria
from .models import Servicio, TipoCambio, VistaInfoAplicantes, VistaPostDetails, Postulacion, Oferta, Estado,VistaConversaciones  
from .models.estado import ABIERTO, CANCELADO, PENDIENTE

# Bounding box del área urbana de Tijuana (excluye Tecate, Rosarito, Ensenada).
# Es un rectángulo aproximado, no el polígono real del municipio.
TIJUANA_LAT_MIN = Decimal('32.40')
TIJUANA_LAT_MAX = Decimal('32.56')
TIJUANA_LON_MIN = Decimal('-117.15')
TIJUANA_LON_MAX = Decimal('-116.78')
UBICACION_FUERA_DE_TIJUANA = 'La ubicación debe estar dentro del área de Tijuana.'


class ServicioSerializer(serializers.ModelSerializer):
    id_cliente = serializers.UUIDField(source='cliente_id')
    id_categoria = serializers.IntegerField(source='categoria_id')
    id_tipo_cambio = serializers.IntegerField(source='tipo_cambio_id', allow_null=True)
    tipo_cambio_nombre = serializers.SerializerMethodField()
    id_estado = serializers.IntegerField(source='estado_id')
    estado_descripcion = serializers.CharField(source='estado.descripcion', read_only=True)

    class Meta:
        model = Servicio
        fields = [
            'id_servicio', 'titulo', 'descripcion', 'precio_inicial',
            'latitud', 'longitud', 'fecha', 'id_estado', 'estado_descripcion',
            'imagenes', 'fecha_final', 'id_cliente', 'id_categoria',
            'id_tipo_cambio', 'tipo_cambio_nombre',
        ]

    def get_tipo_cambio_nombre(self, obj):
        return obj.tipo_cambio.nombre if obj.tipo_cambio_id else None


class CreateServicioSerializer(serializers.ModelSerializer):
    precio_inicial = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=1
    )
    latitud = serializers.DecimalField(
        max_digits=9, decimal_places=6,
        min_value=TIJUANA_LAT_MIN, max_value=TIJUANA_LAT_MAX,
        error_messages={
            'min_value': UBICACION_FUERA_DE_TIJUANA,
            'max_value': UBICACION_FUERA_DE_TIJUANA,
        },
    )
    longitud = serializers.DecimalField(
        max_digits=9, decimal_places=6,
        min_value=TIJUANA_LON_MIN, max_value=TIJUANA_LON_MAX,
        error_messages={
            'min_value': UBICACION_FUERA_DE_TIJUANA,
            'max_value': UBICACION_FUERA_DE_TIJUANA,
        },
    )
    id_categoria = serializers.PrimaryKeyRelatedField(
        source='categoria', queryset=Categoria.objects.all()
    )
    id_tipo_cambio = serializers.PrimaryKeyRelatedField(
        source='tipo_cambio', queryset=TipoCambio.objects.all(),
        required=False, allow_null=True
    )
    imagenes = serializers.ListField(
        child=serializers.URLField(max_length=500), required=False, default=list
    )
    fecha_final = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = Servicio
        fields = [
            'titulo', 'descripcion', 'precio_inicial',
            'latitud', 'longitud', 'fecha','imagenes', 'id_categoria',
            'id_tipo_cambio', 'fecha_final',
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
        validated_data['estado_id'] = ABIERTO
        return Servicio.objects.create(**validated_data)



class UpdateServicioSerializer(serializers.ModelSerializer):
    id_categoria = serializers.PrimaryKeyRelatedField(
        source='categoria', queryset=Categoria.objects.all(), required=False
    )
    imagenes = serializers.ListField(
        child=serializers.URLField(max_length=500), required=False
    )
    precio_inicial = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=1, required=False
    )
    latitud = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False,
        min_value=TIJUANA_LAT_MIN, max_value=TIJUANA_LAT_MAX,
        error_messages={
            'min_value': UBICACION_FUERA_DE_TIJUANA,
            'max_value': UBICACION_FUERA_DE_TIJUANA,
        },
    )
    longitud = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False,
        min_value=TIJUANA_LON_MIN, max_value=TIJUANA_LON_MAX,
        error_messages={
            'min_value': UBICACION_FUERA_DE_TIJUANA,
            'max_value': UBICACION_FUERA_DE_TIJUANA,
        },
    )

    class Meta:
        model = Servicio
        fields = [
            'titulo', 'descripcion', 'precio_inicial',
            'latitud', 'longitud', 'fecha','imagenes', 'id_categoria',
        ]

    def validate_imagenes(self, value):
        usuario = self.context['request'].user
        expected_prefix = (
            f'{settings.SUPABASE_URL}/storage/v1/object/public/'
            f'services_imagenes/user_{usuario.id_usuario}/'
        )
        for url in value:
            if not url.startswith(expected_prefix):
                raise serializers.ValidationError(
                    'Las imágenes deben apuntar a tu propia carpeta en el '
                    'bucket de imágenes de servicios.'
                )
        return value




class InfoAplicanteSerializer(serializers.ModelSerializer):
    class Meta:
        model = VistaInfoAplicantes
        fields = '__all__'


class PostDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = VistaPostDetails
        fields = '__all__'

# Falto el serializer para la lista de servicios, que incluye el nombre de la categoría asociada a cada servicio.
class ServicioListSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
    tipo_cambio_nombre = serializers.SerializerMethodField()
    estado_descripcion = serializers.CharField(source='estado.descripcion', read_only=True)

    class Meta:
        model = Servicio
        fields = [
            'id_servicio', 'titulo', 'precio_inicial', 'latitud',
            'longitud', 'fecha', 'estado_descripcion', 'imagenes',
            'categoria_nombre', 'tipo_cambio_nombre',
        ]

    def get_tipo_cambio_nombre(self, obj):
        return obj.tipo_cambio.nombre if obj.tipo_cambio_id else None




# Oferta y postulacion

class OfertaSerializer(serializers.ModelSerializer):
    id_postulacion = serializers.IntegerField(source='postulacion_id')
    emisor_id = serializers.UUIDField()
    id_estado = serializers.IntegerField(source='estado_id')
    estado_descripcion = serializers.CharField(source='estado.descripcion', read_only=True)

    class Meta:
        model = Oferta
        fields = [
            'id_oferta', 'aceptacion', 'monto', 'fecha', 'id_estado',
            'estado_descripcion', 'comentario', 'id_postulacion', 'emisor_id',
        ]


class CreateOfertaSerializer(serializers.ModelSerializer):
    id_postulacion = serializers.PrimaryKeyRelatedField(
        source='postulacion', queryset=Postulacion.objects.all()
    )
    monto = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1)

    class Meta:
        model = Oferta
        fields = ['id_postulacion', 'monto', 'comentario']

    def validate(self, attrs):
        postulacion = attrs['postulacion']
        usuario = self.context['request'].user
        cliente_id = postulacion.servicio.cliente_id
        proveedor_id = postulacion.proveedor_id
        if usuario.id_usuario not in (cliente_id, proveedor_id):
            raise serializers.ValidationError(
                'No puedes enviar una oferta en una postulación que no te pertenece.'
            )
        return attrs

    def create(self, validated_data):
        validated_data['emisor'] = self.context['request'].user
        validated_data['estado_id'] = PENDIENTE
        validated_data['aceptacion'] = False
        return Oferta.objects.create(**validated_data)



class PostulacionSerializer(serializers.ModelSerializer):
    id_servicio = serializers.IntegerField(source='servicio_id')
    proveedor_id = serializers.UUIDField()
    id_estado = serializers.IntegerField(source='estado_id')
    estado_descripcion = serializers.CharField(source='estado.descripcion', read_only=True)
 
    class Meta:
        model = Postulacion
        fields = [
            'id_postulacion', 'fecha', 'fecha_actualizacion', 'precio_propuesto',
            'mensaje', 'id_estado', 'estado_descripcion', 'proveedor_id', 'id_servicio',
        ]
 
 
class CreatePostulacionSerializer(serializers.ModelSerializer):
    precio_propuesto = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1)
    mensaje = serializers.CharField(required=False, allow_blank=True, allow_null=True)
 
    class Meta:
        model = Postulacion
        fields = ['precio_propuesto', 'mensaje']
 
    def create(self, validated_data):
        validated_data['proveedor'] = self.context['request'].user
        validated_data['servicio'] = self.context['servicio']
        validated_data['estado_id'] = PENDIENTE
        return Postulacion.objects.create(**validated_data)

    
#conversaciones
class ConversacionSerializer(serializers.ModelSerializer):
    no_leidos = serializers.SerializerMethodField()
 
    class Meta:
        model = VistaConversaciones
        fields = [
            'id_conversacion', 'fecha_inicio', 'estado', 'servicio_id', 'servicio_titulo',
            'cliente_id', 'nombre_cliente', 'foto_cliente',
            'proveedor_id', 'nombre_proveedor', 'foto_proveedor',
            'ultimo_mensaje', 'fecha_ultimo_mensaje', 'no_leidos',
        ]
 
    def get_no_leidos(self, obj):
        usuario_id = self.context['request'].user.id_usuario
        if usuario_id == obj.cliente_id:
            return obj.no_leidos_cliente
        return obj.no_leidos_proveedor
 