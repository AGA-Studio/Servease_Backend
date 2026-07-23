from django.conf import settings
from rest_framework import serializers
from .models import Usuario, VistaPerfilCliente, VistaReviewsCliente

ROL_ID_TO_ROLE = {
    1: "client",
    2: "provider",
    3: "admin",
}


class UsuarioSerializer(serializers.ModelSerializer):
    rol = serializers.SerializerMethodField()
    estado = serializers.BooleanField()
    id_categoria = serializers.IntegerField(source='categoria_id', allow_null=True)
    id_empresa = serializers.IntegerField(source='empresa_id', allow_null=True)

    class Meta:
        model = Usuario
        fields = [
            'id_usuario', 'nombre', 'segundo_nombre', 'apellido_pa',
            'apellido_ma', 'correo', 'celular', 'url_foto_perfil',
            'descripcion_perfil', 'fecha_registro', 'estado', 'rol',
            'id_categoria', 'id_empresa',
        ]

    def get_rol(self, obj):
        return ROL_ID_TO_ROLE.get(obj.rol_id, "client")


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


class PerfilClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = VistaPerfilCliente
        fields = '__all__'


class ReviewClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = VistaReviewsCliente
        fields = '__all__'