from django.conf import settings
from rest_framework import serializers

from dashBoard.models.vista_trabajos_disponibles import VistaTrabajosDisponibles
from .models import (
    Categoria,
    Usuario,
    VistaPerfilCliente,
    VistaReviewsCliente,
    VistaHomeCliente,
    VistaResumenGanancias,
    VistaTrabajosAplicados,
    VistaTrabajosDisponibles,
    VistaUltimaResena,
    Notificacion,
    PortafolioProveedor,  
)

ROL_ID_TO_ROLE = {
    1: "client",
    2: "provider",
    3: "admin",
}


class UsuarioSerializer(serializers.ModelSerializer):
    rol = serializers.SerializerMethodField()
    estado = serializers.BooleanField()
    id_categoria = serializers.IntegerField(source='categoria_id', allow_null=True)
    id_categorias = serializers.SerializerMethodField()
    id_empresa = serializers.IntegerField(source='empresa_id', allow_null=True)

    class Meta:
        model = Usuario
        fields = [
            'id_usuario', 'nombre', 'segundo_nombre', 'apellido_pa',
            'apellido_ma', 'correo', 'celular', 'url_foto_perfil',
            'descripcion_perfil', 'fecha_registro', 'estado', 'rol',
            'id_categoria', 'id_categorias', 'id_empresa',
        ]

    def get_rol(self, obj):
        return ROL_ID_TO_ROLE.get(obj.rol_id, "client")

    def get_id_categorias(self, obj):
        return list(obj.areas_trabajo.values('id_categoria', 'nombre'))


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6, write_only=True)
    nombre = serializers.CharField(max_length=100)
    segundo_nombre = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    apellido_pa = serializers.CharField(max_length=100)
    apellido_ma = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    photo = serializers.ImageField(required=False, allow_null=True)


class UpdateProfilePhotoSerializer(serializers.Serializer):
    url_foto_perfil = serializers.URLField(max_length=200)

    def validate_url_foto_perfil(self, value):
        usuario = self.context['request'].user
        expected_prefix = (
            f'{settings.SUPABASE_URL}/storage/v1/object/public/'
            f'profile_photos/user_{usuario.id_usuario}/'
        )
        if not value.startswith(expected_prefix):
            raise serializers.ValidationError(
                'La URL debe apuntar a tu propia carpeta en el bucket de fotos de perfil.'
            )
        return value

class UpdatePersonalInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = [
            'nombre', 'segundo_nombre', 'apellido_pa', 'apellido_ma',
            'celular', 'descripcion_perfil',
        ]


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id_categoria', 'nombre']


class PerfilClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = VistaPerfilCliente
        fields = '__all__'


class ReviewClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = VistaReviewsCliente
        fields = '__all__'

class HomeClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = VistaHomeCliente
        fields = '__all__'


 
class DisponibilidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['disponible']
 
 
class AreasTrabajoSerializer(serializers.Serializer):
    categorias = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Categoria.objects.all()
    )
 
    def save(self, **kwargs):
        usuario = self.context['request'].user
        usuario.areas_trabajo.set(self.validated_data['categorias'])
        return usuario
 
 
class ResumenGananciasSerializer(serializers.ModelSerializer):
    class Meta:
        model = VistaResumenGanancias
        fields = '__all__'
 
 
class TrabajoAplicadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VistaTrabajosAplicados
        fields = '__all__'


class TrabajoAplicadoCardSerializer(serializers.ModelSerializer):
    """Shape reducido para las cards de 'mis propuestas' del proveedor."""
    presupuesto = serializers.DecimalField(
        source='precio_final', max_digits=10, decimal_places=2
    )

    class Meta:
        model = VistaTrabajosAplicados
        fields = [
            'id_postulacion', 'categoria', 'estado', 'titulo',
            'tiempo_transcurrido', 'presupuesto', 'foto',
        ]


class TrabajoDisponibleSerializer(serializers.ModelSerializer):
    class Meta:
        model = VistaTrabajosDisponibles
        fields = '__all__'

class UltimaResenaSerializer(serializers.ModelSerializer):
    class Meta:
        model = VistaUltimaResena
        fields = '__all__'

class NotificacionSerializer(serializers.ModelSerializer):
    id_usuario = serializers.UUIDField(source='usuario_id', read_only=True)
 
    class Meta:
        model = Notificacion
        fields = [
            'id_notificacion', 'id_usuario', 'tipo', 'titulo', 'contenido',
            'leido', 'fecha', 'referencia_tabla', 'referencia_id',
        ]

#Portafolio Proveedor Serializer
class PortafolioSerializer(serializers.ModelSerializer):
    id_proveedor = serializers.UUIDField(source='proveedor_id')
    id_categoria = serializers.IntegerField(source='categoria_id')
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
 
    class Meta:
        model = PortafolioProveedor
        fields = [
            'id_portafolio', 'titulo', 'descripcion', 'fotos', 'fecha',
            'id_proveedor', 'id_categoria', 'categoria_nombre',
        ]
 
 
class CreatePortafolioSerializer(serializers.ModelSerializer):
    id_categoria = serializers.PrimaryKeyRelatedField(
        source='categoria', queryset=Categoria.objects.all()
    )
    fotos = serializers.ListField(
        child=serializers.URLField(max_length=500), required=False, default=list
    )
 
    class Meta:
        model = PortafolioProveedor
        fields = ['titulo', 'descripcion', 'id_categoria', 'fotos']
 
    def validate_fotos(self, value):
        usuario = self.context['request'].user
        expected_prefix = (
            f'{settings.SUPABASE_URL}/storage/v1/object/public/'
            f'portafolio_fotos/user_{usuario.id_usuario}/'
        )
        for url in value:
            if not url.startswith(expected_prefix):
                raise serializers.ValidationError(
                    'Las fotos deben apuntar a tu propia carpeta en el '
                    'bucket de fotos de portafolio.'
                )
        return value
 
    def create(self, validated_data):
        validated_data['proveedor'] = self.context['request'].user
        return PortafolioProveedor.objects.create(**validated_data)
 